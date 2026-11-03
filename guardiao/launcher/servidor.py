"""Servidor local do protótipo: entrega a página e transmite a varredura ao vivo (SSE)."""

import json
import secrets
import subprocess
import tempfile
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import eventos, regras_yara, scanner, varredura
from . import demo

PASTA_ESTATICA = Path(__file__).parent / "estatico"
ESTATICOS = {
    "index.html": "text/html; charset=utf-8",
    "estilo.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
ALVOS = ("rapida", "completa", "pasta", "demo")   # a página escolhe por nome, nunca por caminho

# Pastas escolhidas no seletor, guardadas aqui: a página só recebe um id.
# Assim nenhum site aberto no navegador consegue pedir "varra /tal/caminho".
PASTAS: dict[str, Path] = {}


def escolher_pasta() -> Path | None:
    """Abre o seletor de pastas do sistema. None se a pessoa cancelar."""
    r = subprocess.run(
        ["zenity", "--file-selection", "--directory", "--title=Qual pasta os guardiões devem patrulhar?"],
        capture_output=True, text=True,
    )
    caminho = Path(r.stdout.strip())
    return caminho if r.returncode == 0 and caminho.is_dir() else None


class Manipulador(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._estatico("index.html")
        elif url.path.startswith("/estatico/") and url.path.removeprefix("/estatico/") in ESTATICOS:
            self._estatico(url.path.removeprefix("/estatico/"))
        elif url.path == "/api/varrer":
            if not self._host_local():
                return
            params = parse_qs(url.query)
            alvo = params.get("alvo", [""])[0]
            pasta = PASTAS.get(params.get("id", [""])[0])
            if alvo not in ALVOS:
                self.send_error(400, "alvo inválido")
            elif alvo == "pasta" and pasta is None:
                self.send_error(400, "pasta não escolhida")
            else:
                self._varrer(alvo, pasta)
        else:
            self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/escolher-pasta":
            self.send_error(404)
            return
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not self._host_local():
            return
        # Exigir JSON barra outros sites: um <form> não sabe mandar application/json,
        # e um fetch de outra origem com esse tipo pede permissão (CORS) que nunca damos.
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "envie application/json")
            return
        try:
            pasta = escolher_pasta()
        except FileNotFoundError:
            self.send_error(501, "zenity não instalado")
            return
        if pasta is None:
            self._json({"cancelado": True})
        else:
            id_ = secrets.token_urlsafe(9)
            PASTAS[id_] = pasta
            self._json({"id": id_, "nome": pasta.name or str(pasta)})

    def log_message(self, format, *args):
        pass   # sem uma linha no terminal para cada requisição

    def _host_local(self) -> bool:
        # Contra DNS rebinding: um site malicioso pode fazer o próprio domínio
        # apontar para 127.0.0.1, mas o cabeçalho Host continua sendo o dele.
        porta = self.server.server_address[1]
        if self.headers.get("Host") in (f"127.0.0.1:{porta}", f"localhost:{porta}"):
            return True
        self.send_error(403)
        return False

    def _estatico(self, nome: str) -> None:
        corpo = (PASTA_ESTATICA / nome).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ESTATICOS[nome])
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados: dict) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _varrer(self, alvo: str, pasta: Path | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            if alvo == "demo":
                with tempfile.TemporaryDirectory(prefix="guardiao-demo-") as tmp:
                    self._transmitir([demo.criar_amostras(Path(tmp))], "Demonstração", usar_cache=False)
            elif alvo == "pasta" and pasta is not None:
                self._transmitir([pasta], pasta.name or str(pasta))
            elif alvo == "rapida":
                self._transmitir(varredura.raizes_rapida(), "os locais preferidos dos invasores")
            else:
                self._transmitir(varredura.raizes_completa(), "o computador inteiro")
        except (BrokenPipeError, ConnectionResetError):
            pass   # a página fechou ou apertou Parar

    def _transmitir(self, raizes: list[Path], rotulo: str, usar_cache: bool = True) -> None:
        base = raizes[0] if len(raizes) == 1 else None
        self._evento({"tipo": "inicio", "alvo": rotulo, "yara": regras_yara.disponivel()})
        # closing(): se a página sumir, o erro de escrita sai do laço e o gerador
        # é fechado na hora, o que encerra os processos de análise.
        with closing(varredura.executar(raizes, usar_cache=usar_cache)) as itens:
            for item in itens:
                if isinstance(item, varredura.Progresso):
                    self._evento({"tipo": "progresso", "fase": item.fase, "vistos": item.vistos,
                                  "total": item.total,
                                  "atual": eventos.relativo(item.atual, base) if item.atual else ""})
                elif isinstance(item, scanner.Resultado) and (item.infectado or item.suspeito):
                    self._evento(eventos.de_resultado(item, base))
                elif isinstance(item, varredura.Resumo):
                    self._evento({"tipo": "fim", "ameaca": item.ameacas, "suspeito": item.suspeitos,
                                  "total": item.analisados + item.em_cache, "em_cache": item.em_cache,
                                  "sem_permissao": item.sem_permissao, "grandes": item.grandes,
                                  "segundos": round(item.segundos, 1)})

    def _evento(self, dados: dict) -> None:
        self.wfile.write(f"data: {json.dumps(dados, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()


def criar_servidor(porta: int = 8765) -> ThreadingHTTPServer:
    # Só 127.0.0.1: com 0.0.0.0 qualquer um na mesma rede poderia disparar varreduras.
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    servidor.daemon_threads = True
    return servidor
