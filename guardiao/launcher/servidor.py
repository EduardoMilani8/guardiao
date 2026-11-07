"""Servidor local do painel: entrega a página e transmite a varredura ao vivo (SSE)."""

import json
import secrets
import subprocess
import threading
import time
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import bases, eventos, historico, quarentena, regras_yara, scanner, varredura
from . import estado

PASTA_ESTATICA = Path(__file__).parent / "estatico"
TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}
ALVOS = ("rapida", "completa", "pasta")   # a página escolhe por nome, nunca por caminho
MAX_HISTORICO = 500


def estaticos() -> dict[str, Path]:
    """Os arquivos que a página pode pedir, montados uma vez a partir da pasta:
    nada fora dela é servido, nem com "../" no endereço."""
    return {str(p.relative_to(PASTA_ESTATICA)): p for p in PASTA_ESTATICA.rglob("*")
            if p.is_file() and p.suffix in TIPOS}


ESTATICOS = estaticos()

# Pastas escolhidas no seletor, guardadas aqui: a página só recebe um id.
# Assim nenhum site aberto no navegador consegue pedir "varra /tal/caminho".
PASTAS: dict[str, Path] = {}

# Achados que o próprio servidor viu (numa varredura ou no histórico): a página
# pede "tranque o achado X7f..." e nunca "tranque /tal/caminho". Um site aberto
# no navegador não tem como inventar um id que o servidor não deu.
ACHADOS: dict[str, dict] = {}
_trava = threading.Lock()

# A última caçada fica guardada enquanto o painel estiver aberto.
CACADA: dict = {}


def guardar_achado(caminho: str, sha256: str, nome: str | None, camada: str | None = None,
                   veredito: str = "ameaca") -> str:
    with _trava:
        for id_, a in ACHADOS.items():
            if a["caminho"] == caminho and a["sha256"] == sha256:
                return id_
        id_ = secrets.token_urlsafe(12)
        ACHADOS[id_] = {"caminho": caminho, "sha256": sha256, "ameaca": nome, "camada": camada,
                        "veredito": veredito}
        return id_


class Recusado(Exception):
    def __init__(self, status: int, motivo: str):
        super().__init__(motivo)
        self.status, self.motivo = status, motivo


def isolar(id_: str) -> dict:
    """Tranca um achado já visto, se o arquivo ainda é exatamente o que foi analisado."""
    with _trava:
        dados = ACHADOS.get(id_)
    if dados is None:
        raise Recusado(404, "achado desconhecido")
    caminho = Path(dados["caminho"])
    if not caminho.is_file() or caminho.is_symlink():
        raise Recusado(410, "o arquivo não está mais lá")
    try:
        # Mesmo conteúdo da varredura: se ele mudou, a decisão precisa ser de novo.
        if scanner.calcular_sha256(caminho) != dados["sha256"]:
            raise Recusado(409, "o arquivo mudou desde a varredura: varra de novo")
        motivo = dados["ameaca"] or ("suspeito" if dados["veredito"] == "suspeito" else "ameaça")
        id_cela = quarentena.isolar(caminho, dados["sha256"], motivo,
                                    camada=dados["camada"], veredito=dados["veredito"])
    except PermissionError:
        raise Recusado(403, "sem permissão: é um arquivo do sistema, use "
                            "sudo .venv/bin/python -m guardiao varrer --isolar")
    except OSError as erro:
        raise Recusado(500, erro.strerror or str(erro))
    historico.marcar_isolado(dados["caminho"], dados["sha256"], id_cela)
    with _trava:
        ACHADOS.pop(id_, None)
    return {"quarentena": id_cela, "caminho": dados["caminho"]}


def _achado_publico(r: historico.Registro, a: dict) -> dict:
    return {"id": guardar_achado(a["caminho"], a["sha256"], a["ameaca"], a.get("camada"), a["veredito"]),
            "caminho": a["caminho"], "nome": Path(a["caminho"]).name, "ameaca": a["ameaca"],
            "veredito": a["veredito"], "camada": a.get("camada"), "motivos": a.get("motivos", []),
            "quando": r.inicio, "origem": r.origem}


def pendentes(registros: list[historico.Registro]) -> list[dict]:
    """Ameaças de qualquer varredura que continuam no lugar, e os suspeitos da
    última: suspeito que ninguém trancou não fica pedindo atenção para sempre."""
    lista = [_achado_publico(r, a) for r, a in historico.pendentes(registros)]
    if registros:
        ultimo = registros[0]
        lista += [_achado_publico(ultimo, a) for a in ultimo.achados
                  if a.get("veredito") == "suspeito" and not a.get("quarentena")
                  and Path(a["caminho"]).is_file() and not Path(a["caminho"]).is_symlink()]
    return lista


def resumo_do_historico() -> dict:
    registros = historico.listar(MAX_HISTORICO)
    return {
        "registros": [{"inicio": r.inicio, "tipo": r.tipo, "origem": r.origem, "total": r.total,
                       "ameacas": r.ameacas, "suspeitos": r.suspeitos, "segundos": r.segundos,
                       "sem_permissao": r.sem_permissao, "root": r.root,
                       "achados": [{"nome": Path(a["caminho"]).name, "veredito": a["veredito"],
                                    "camada": a.get("camada"), "trancado": bool(a.get("quarentena"))}
                                   for a in r.achados]}
                      for r in registros],
        "pendentes": pendentes(registros),
    }


def lista_da_quarentena() -> list[dict]:
    return sorted(({"id": e["id"], "nome": Path(e.get("original", "")).name, "original": e.get("original"),
                    "motivo": e.get("motivo"), "camada": e.get("camada"),
                    "veredito": e.get("veredito") or "ameaca", "data": e.get("data"),
                    "tamanho": e.get("tamanho", 0)} for e in quarentena.listar()),
                  key=lambda e: e["data"] or "", reverse=True)


def devolver(id_: str) -> dict:
    try:
        return {"caminho": str(quarentena.restaurar(id_))}
    except quarentena.NaoEncontrado:
        raise Recusado(404, "nada com esse id na quarentena")
    except FileExistsError:
        raise Recusado(409, "já existe outro arquivo no lugar de onde ele veio")
    except PermissionError:
        raise Recusado(403, "sem permissão para devolver para a pasta de origem")


def apagar(id_: str) -> dict:
    try:
        return {"apagado": quarentena.apagar(id_).get("original")}
    except quarentena.NaoEncontrado:
        raise Recusado(404, "nada com esse id na quarentena")
    except PermissionError:
        raise Recusado(403, "sem permissão para apagar")


def cacar() -> dict:
    """A caçada do Vidente. Só olha: não apaga nem muda nada."""
    from .. import assinaturas, cacador, clamav
    julgar = cacador.Juiz(assinaturas.carregar(), regras_yara.carregar(), clamav.conectar())
    achados = cacador.cacar(julgar)
    CACADA.clear()
    CACADA.update({
        "quando": time.time(),
        "achados": [{"gravidade": a.gravidade, "categoria": a.categoria, "arquivo": str(a.arquivo),
                     "mensagem": a.mensagem} for a in achados if a.gravidade != "info"],
    })
    return CACADA


def atualizar_bases() -> dict:
    try:
        relatorios = bases.atualizar(bases.registradas())
    except bases.Ocupado:
        raise Recusado(409, "uma atualização já está rodando: espere um pouco")
    return {"bases": [{"base": r.base, "situacao": r.situacao, "erro": r.estado.erro} for r in relatorios]}


def escolher_pasta() -> Path | None:
    """Abre o seletor de pastas do sistema. None se a pessoa cancelar."""
    r = subprocess.run(
        ["zenity", "--file-selection", "--directory", "--title=Qual pasta a Guarnição deve patrulhar?"],
        capture_output=True, text=True,
    )
    caminho = Path(r.stdout.strip())
    return caminho if r.returncode == 0 and caminho.is_dir() else None


def escolher() -> dict:
    try:
        pasta = escolher_pasta()
    except FileNotFoundError:
        raise Recusado(501, "zenity não instalado")
    if pasta is None:
        return {"cancelado": True}
    id_ = secrets.token_urlsafe(9)
    PASTAS[id_] = pasta
    return {"id": id_, "nome": pasta.name or str(pasta)}


# Rotas POST: todas recebem JSON; as que agem num item recebem {"id": ...}.
ACOES = {
    "/api/isolar": lambda d: isolar(str(d.get("id"))),
    "/api/devolver": lambda d: devolver(str(d.get("id"))),
    "/api/apagar": lambda d: apagar(str(d.get("id"))),
    "/api/escolher-pasta": lambda d: escolher(),
    "/api/cacar": lambda d: cacar(),
    "/api/atualizar": lambda d: atualizar_bases(),
}


class Manipulador(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._estatico("index.html")
        elif url.path.startswith("/estatico/") and url.path.removeprefix("/estatico/") in ESTATICOS:
            self._estatico(url.path.removeprefix("/estatico/"))
        elif url.path in ("/api/estado", "/api/historico", "/api/quarentena"):
            if self._host_local():
                self._json({
                    "/api/estado": lambda: estado.montar() | {"cacada": CACADA or None},
                    "/api/historico": resumo_do_historico,
                    "/api/quarentena": lambda: {"itens": lista_da_quarentena()},
                }[url.path]())
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
        if rota not in ACOES:
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
        try:
            dados = json.loads(corpo or b"{}")
            if not isinstance(dados, dict):
                raise ValueError
            self._json(ACOES[rota](dados))
        except Recusado as erro:
            self._json({"erro": erro.motivo}, erro.status)
        except ValueError:
            self._json({"erro": "pedido inválido"}, 400)

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
        arquivo = ESTATICOS[nome]
        corpo = arquivo.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS[arquivo.suffix])
        self.send_header("Content-Length", str(len(corpo)))
        # Fontes e retratos não mudam entre versões do mesmo dia; a página e o código sim.
        self.send_header("Cache-Control", "max-age=86400" if arquivo.suffix in (".woff2",) else "no-store")
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
            if alvo == "pasta" and pasta is not None:
                self._transmitir([pasta], pasta.name or str(pasta), tipo=str(pasta))
            elif alvo == "rapida":
                self._transmitir(varredura.raizes_rapida(), "rápida", tipo="rápida")
            else:
                self._transmitir(varredura.raizes_completa(), "completa", tipo="completa")
        except (BrokenPipeError, ConnectionResetError):
            pass   # a página fechou ou apertou Parar

    def _transmitir(self, raizes: list[Path], rotulo: str, tipo: str) -> None:
        base = raizes[0] if len(raizes) == 1 else None
        inicio, achados = datetime.now(), []
        self._evento({"tipo": "inicio", "alvo": rotulo, "yara": regras_yara.disponivel(),
                      "avisos": bases.avisos()})
        # closing(): se a página sumir, o erro de escrita sai do laço e o gerador
        # é fechado na hora, o que encerra os processos de análise.
        with closing(varredura.executar(raizes)) as itens:
            for item in itens:
                if isinstance(item, varredura.Progresso):
                    self._evento({"tipo": "progresso", "fase": item.fase, "vistos": item.vistos,
                                  "total": item.total,
                                  "atual": eventos.relativo(item.atual, base) if item.atual else ""})
                elif isinstance(item, scanner.Resultado) and (item.infectado or item.suspeito):
                    evento = eventos.de_resultado(item, base)
                    evento["isolar"] = guardar_achado(str(item.caminho), item.sha256, item.ameaca,
                                                      item.camada, evento["veredito"])
                    evento["completo"] = str(item.caminho)
                    achados.append(historico.achado(item))
                    self._evento(evento)
                elif isinstance(item, varredura.Resumo):
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
