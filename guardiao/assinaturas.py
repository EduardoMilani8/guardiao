"""Banco de assinaturas: SHA-256 de arquivos maliciosos conhecidos."""

from pathlib import Path

ARQUIVO_PADRAO = Path(__file__).parent.parent / "assinaturas" / "hashes.txt"


def carregar(caminho: Path = ARQUIVO_PADRAO) -> dict[str, str]:
    """Lê o banco no formato `<sha256> <nome da ameaça>`, uma por linha.

    Linhas vazias e começando com `#` são ignoradas.
    Retorna {hash: nome}.
    """
    banco: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        hash_hex, _, nome = linha.partition(" ")
        banco[hash_hex.lower()] = nome.strip() or "Desconhecido"
    return banco
