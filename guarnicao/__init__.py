"""Guarnição: antivírus para Linux."""

import sys

__version__ = "0.1.0"


def conferir_python(versao=sys.version_info) -> None:
    """A Guarnição usa tomllib (3.11+). Num Python mais velho (Ubuntu 22.04 vem
    com 3.10) o erro seria um traceback longe da causa; aqui ele fica claro."""
    if tuple(versao[:2]) < (3, 11):
        raise SystemExit(
            f"A Guarnição precisa do Python 3.11 ou mais novo, e este é o {versao[0]}.{versao[1]}. "
            "Instale o 3.11 (sudo apt install python3.11 python3.11-venv) e recrie o ambiente: "
            "rm -rf .venv && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt")


conferir_python()
