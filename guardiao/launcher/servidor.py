"""Servidor local do protótipo: entrega a página e transmite a varredura ao vivo (SSE)."""

import json
import secrets
import subprocess
import tempfile
import threading
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import bases, eventos, historico, quarentena, regras_yara, scanner, varredura
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

# Ameaças que o próprio servidor achou (numa varredura ou no histórico): a página
# pede "tranque a ameaça X7f..." e nunca "tranque /tal/caminho". Um site aberto
# no navegador não tem como inventar um id que o servidor não deu.
AMEACAS: dict[str, dict] = {}
_trava = threading.Lock()


def guardar_ameaca(caminho: str, sha256: str, nome: str | None) -> str:
    with _trava:
        for id_, a in AMEACAS.items():
            if a["caminho"] == caminho and a["sha256"] == sha256:
                return id_
        id_ = secrets.token_urlsafe(12)
        AMEACAS[id_] = {"caminho": caminho, "sha256": sha256, "ameaca": nome}
        return id_


class NaoIsolado(Exception):
    def __init__(self, status: int, motivo: str):
        super().__init__(motivo)
        self.status, self.motivo = status, motivo


def isolar(id_: str) -> dict:
    """Tranca uma ameaça já vista, se o arquivo ainda é exatamente o que foi analisado."""
    with _trava:
        dados = AMEACAS.get(id_)
    if dados is None:
        raise NaoIsolado(404, "ameaça desconhecida")
    caminho = Path(dados["caminho"])
    if not caminho.is_file() or caminho.is_symlink():
        raise NaoIsolado(410, "o arquivo não está mais lá")
    try:
        # Mesmo conteúdo da varredura: se ele mudou, a decisão precisa ser de novo.
        if scanner.calcular_sha256(caminho) != dados["sha256"]:
            raise NaoIsolado(409, "o arquivo mudou desde a varredura: varra de novo")
        id_cela = quarentena.isolar(caminho, dados["sha256"], dados["ameaca"] or "ameaça")
    except PermissionError:
        raise NaoIsolado(403, "sem permissão: é um arquivo do sistema, use "
                              "sudo .venv/bin/python -m guardiao varrer --isolar")
    except OSError as erro:
        raise NaoIsolado(500, erro.strerror or str(erro))
    historico.marcar_isolado(dados["caminho"], dados["sha256"], id_cela)
    with _trava:
        AMEACAS.pop(id_, None)
    return {"quarentena": id_cela, "caminho": dados["caminho"]}


def resumo_do_historico(quantos: int = 8) -> dict:
    registros = historico.listar(50)
    ultimas = {}
    for tipo in ("rápida", "completa"):
        r = next((r for r in registros if r.tipo == tipo), None) or historico.ultima(tipo)
        ultimas[tipo] = r.inicio if r else None
    return {
        "ultimas": ultimas,
        "registros": [{"inicio": r.inicio, "tipo": r.tipo, "origem": r.origem, "total": r.total,
                       "ameacas": r.ameacas, "suspeitos": r.suspeitos, "segundos": r.segundos}
                      for r in registros[:quantos]],
        "pendentes": [{"id": guardar_ameaca(a["caminho"], a["sha256"], a["ameaca"]), "caminho": a["caminho"],
                       "nome": Path(a["caminho"]).name, "ameaca": a["ameaca"], "quando": r.inicio,
                       "origem": r.origem}
                      for r, a in historico.pendentes(registros)],
    }


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
        elif url.path == "/api/historico":
            if self._host_local():
                self._json(resumo_do_historico())
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
        rota = urlparse(self.path).path
        if rota not in ("/api/escolher-pasta", "/api/isolar"):
            self.send_error(404)
            return
        corpo = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 4096))
        if not self._host_local():
            return
        # Exigir JSON barra outros sites: um <form> não sabe mandar application/json,
        # e um fetch de outra origem com esse tipo pede permissão (CORS) que nunca damos.
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "envie application/json")
            return
        if rota == "/api/isolar":
            try:
                id_ = json.loads(corpo or b"{}").get("id")
                self._json(isolar(str(id_)))
            except NaoIsolado as erro:
                self._json({"erro": erro.motivo}, erro.status)
            except (ValueError, AttributeError):
                self._json({"erro": "pedido inválido"}, 400)
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

    def _json(self, dados: dict, status: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(status)
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
                self._transmitir([pasta], pasta.name or str(pasta), tipo=str(pasta))
            elif alvo == "rapida":
                self._transmitir(varredura.raizes_rapida(), "os locais preferidos dos invasores", tipo="rápida")
            else:
                self._transmitir(varredura.raizes_completa(), "o computador inteiro", tipo="completa")
        except (BrokenPipeError, ConnectionResetError):
            pass   # a página fechou ou apertou Parar

    def _transmitir(self, raizes: list[Path], rotulo: str, usar_cache: bool = True,
                    tipo: str | None = None) -> None:
        """`tipo` None: não vai para o histórico (a demonstração)."""
        base = raizes[0] if len(raizes) == 1 else None
        inicio, achados = datetime.now(), []
        self._evento({"tipo": "inicio", "alvo": rotulo, "yara": regras_yara.disponivel(),
                      "avisos": bases.avisos()})
        # closing(): se a página sumir, o erro de escrita sai do laço e o gerador
        # é fechado na hora, o que encerra os processos de análise.
        with closing(varredura.executar(raizes, usar_cache=usar_cache)) as itens:
            for item in itens:
                if isinstance(item, varredura.Progresso):
                    self._evento({"tipo": "progresso", "fase": item.fase, "vistos": item.vistos,
                                  "total": item.total,
                                  "atual": eventos.relativo(item.atual, base) if item.atual else ""})
                elif isinstance(item, scanner.Resultado) and (item.infectado or item.suspeito):
                    evento = eventos.de_resultado(item, base)
                    if item.infectado and tipo is not None:   # a demonstração some ao terminar
                        evento["isolar"] = guardar_ameaca(str(item.caminho), item.sha256, item.ameaca)
                    achados.append(historico.achado(item))
                    self._evento(evento)
                elif isinstance(item, varredura.Resumo):
                    if tipo is not None:
                        historico.registrar(historico.novo(tipo, "launcher", inicio, item, achados))
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
