"""Servidor local do protótipo: entrega a página e transmite a varredura ao vivo (SSE)."""

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import assinaturas, eventos, regras_yara, scanner
from . import demo

PASTA_ESTATICA = Path(__file__).parent / "estatico"
ESTATICOS = {
    "index.html": "text/html; charset=utf-8",
    "estilo.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
ALVOS = ("downloads", "demo")   # a página escolhe por nome, nunca por caminho


class Manipulador(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._estatico("index.html")
        elif url.path.startswith("/estatico/") and url.path.removeprefix("/estatico/") in ESTATICOS:
            self._estatico(url.path.removeprefix("/estatico/"))
        elif url.path == "/api/varrer":
            alvo = parse_qs(url.query).get("alvo", [""])[0]
            if alvo not in ALVOS:
                self.send_error(400, "alvo inválido")
            else:
                self._varrer(alvo)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass   # sem uma linha no terminal para cada requisição

    def _estatico(self, nome: str) -> None:
        corpo = (PASTA_ESTATICA / nome).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ESTATICOS[nome])
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _varrer(self, alvo: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            if alvo == "demo":
                with tempfile.TemporaryDirectory(prefix="guardiao-demo-") as tmp:
                    self._transmitir(demo.criar_amostras(Path(tmp)), "Demonstração")
            else:
                self._transmitir(Path.home() / "Downloads", "Downloads")
        except (BrokenPipeError, ConnectionResetError):
            pass   # a página foi fechada no meio da varredura

    def _transmitir(self, pasta: Path, rotulo: str) -> None:
        banco = assinaturas.carregar()
        yara = regras_yara.carregar()   # criado nesta thread: o Scanner do YARA-X não troca de thread
        total = sum(1 for _ in scanner.listar_arquivos(pasta)) if pasta.is_dir() else 0
        self._evento({"tipo": "inicio", "alvo": rotulo, "total": total, "yara": yara is not None})

        contagem = {"ameaca": 0, "suspeito": 0, "limpo": 0}
        if pasta.is_dir():
            for item in scanner.varrer(pasta, banco, yara):
                if isinstance(item, tuple):
                    self._evento(eventos.de_erro(*item, pasta))
                    continue
                evento = eventos.de_resultado(item, pasta)
                contagem[evento["veredito"]] += 1
                self._evento(evento)
        self._evento({"tipo": "fim", **contagem})

    def _evento(self, dados: dict) -> None:
        self.wfile.write(f"data: {json.dumps(dados, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()


def criar_servidor(porta: int = 8765) -> ThreadingHTTPServer:
    # Só 127.0.0.1: com 0.0.0.0 qualquer um na mesma rede poderia disparar varreduras.
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    servidor.daemon_threads = True
    return servidor
