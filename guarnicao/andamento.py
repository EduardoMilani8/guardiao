"""O andamento da varredura que está rodando, para o escudo da barra ir enchendo.

Um arquivo pequeno em ~/.cache/guarnicao/progresso.json, gravado durante a
varredura e apagado no fim. Se a varredura morrer no meio, o pid dele não
existe mais e ler() devolve None: o escudo nunca fica preso em "procurando".
"""

import json
import os
import signal
from pathlib import Path

from .caminhos import casa_real

ARQUIVO = Path(os.environ.get("XDG_CACHE_HOME", casa_real() / ".cache")) / "guarnicao" / "progresso.json"


def gravar(tipo: str, feitos: int, total: int, arquivo: Path | None = None) -> None:
    arquivo = arquivo or ARQUIVO
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps({"pid": os.getpid(), "tipo": tipo, "feitos": feitos, "total": total}))
        temporario.replace(arquivo)
    except OSError:
        pass   # sem andamento o escudo só não enche; a varredura segue


def apagar(arquivo: Path | None = None) -> None:
    try:
        (arquivo or ARQUIVO).unlink()
    except OSError:
        pass


def _linha_de_comando(pid: int) -> list[str]:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


def ler(arquivo: Path | None = None) -> dict | None:
    try:
        dados = json.loads((arquivo or ARQUIVO).read_text())
        pid = int(dados["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    comando = _linha_de_comando(pid)
    if not any("guarnicao" in parte for parte in comando):
        # O processo não existe mais, ou o número dele foi reaproveitado por outro
        # programa: a varredura morreu no meio.
        return None
    # Só a varredura do terminal ou do timer pode ser parada: a do launcher roda
    # dentro dele, e parar o pid seria fechar o painel.
    dados["pode_parar"] = "guarnicao" in comando and "varrer" in comando
    return dados


def parar(arquivo: Path | None = None) -> bool:
    dados = ler(arquivo)
    if not dados or not dados["pode_parar"]:
        return False
    try:
        os.kill(int(dados["pid"]), signal.SIGTERM)
    except OSError:
        return False
    return True
