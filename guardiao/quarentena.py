"""Quarentena: isola arquivos perigosos sem apagá-los."""

import json
import os
import shutil
import stat
import uuid
from datetime import datetime
from pathlib import Path

PASTA_PADRAO = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "guardiao" / "quarentena"


def isolar(caminho: Path, sha256: str, motivo: str, pasta: Path = PASTA_PADRAO) -> str:
    """Move o arquivo para a quarentena, sem permissão de execução.

    Retorna o id da entrada, usado para restaurar depois.
    """
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    id_ = uuid.uuid4().hex[:12]
    destino = pasta / f"{id_}.bloqueado"

    shutil.move(caminho, destino)
    os.chmod(destino, stat.S_IRUSR)   # só leitura pelo dono, nunca executável

    (pasta / f"{id_}.json").write_text(json.dumps({
        "original": str(caminho.resolve()),
        "sha256": sha256,
        "motivo": motivo,
        "data": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2))
    return id_


def listar(pasta: Path = PASTA_PADRAO) -> list[dict]:
    if not pasta.exists():
        return []
    entradas = []
    for meta in sorted(pasta.glob("*.json")):
        dados = json.loads(meta.read_text())
        dados["id"] = meta.stem
        entradas.append(dados)
    return entradas


def restaurar(id_: str, pasta: Path = PASTA_PADRAO) -> Path:
    meta = pasta / f"{id_}.json"
    dados = json.loads(meta.read_text())
    original = Path(dados["original"])
    if original.exists():
        raise FileExistsError(f"Já existe um arquivo em {original}")

    original.parent.mkdir(parents=True, exist_ok=True)
    bloqueado = pasta / f"{id_}.bloqueado"
    os.chmod(bloqueado, stat.S_IRUSR | stat.S_IWUSR)  # permissão de execução não volta
    shutil.move(bloqueado, original)
    meta.unlink()
    return original
