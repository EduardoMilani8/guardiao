"""Banco de assinaturas: SHA-256 de arquivos maliciosos conhecidos.

Junta duas fontes:
- `assinaturas/hashes.txt`, pequeno e mantido à mão (ex.: EICAR);
- os `hashes.sqlite` das bases baixadas (ex.: MalwareBazaar), que podem ter
  milhões de linhas. Esses são consultados direto do disco: o sistema guarda
  em memória só as páginas mais usadas, e as compartilha entre os processos
  da varredura, em vez de cada processo carregar tudo num dicionário.
"""

import sqlite3
import time
from pathlib import Path
from typing import Callable, Iterable

ARQUIVO_PADRAO = Path(__file__).parent.parent / "assinaturas" / "hashes.txt"
NOME_SQLITE = "hashes.sqlite"
RECONFERIR_BASES = 60   # segundos: o monitor fica dias aberto e precisa ver bases novas


def ler_txt(caminho: Path = ARQUIVO_PADRAO) -> dict[str, str]:
    """Lê o formato `<sha256> <nome da ameaça>`, uma por linha.

    Linhas vazias e começando com `#` são ignoradas.
    """
    banco: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        hash_hex, _, nome = linha.partition(" ")
        banco[hash_hex.lower()] = nome.strip() or "Desconhecido"
    return banco


def criar_sqlite(destino: Path, pares: Iterable[tuple[str, str]]) -> int:
    """Grava (ou acrescenta a) um banco de hashes de uma base. Devolve o total."""
    db = sqlite3.connect(destino)
    try:
        # WITHOUT ROWID: a própria chave é o índice, sem uma cópia a mais dos hashes.
        db.execute("CREATE TABLE IF NOT EXISTS hashes (sha256 TEXT PRIMARY KEY, nome TEXT) WITHOUT ROWID")
        db.executemany("INSERT OR IGNORE INTO hashes VALUES (?, ?)", ((s.lower(), n) for s, n in pares))
        db.commit()
        return db.execute("SELECT count(*) FROM hashes").fetchone()[0]
    finally:
        db.close()


def _fontes_das_bases() -> list[Path]:
    from . import bases   # aqui dentro: bases importa caminhos, e nada daqui
    fontes = []
    for base in bases.registradas():
        pasta = bases.atual(base)
        if pasta and (pasta / NOME_SQLITE).is_file():
            fontes.append(pasta / NOME_SQLITE)
    return fontes


class Banco:
    """Responde `get(sha256) -> nome da ameaça ou None`, como um dicionário."""

    def __init__(self, locais: dict[str, str],
                 fontes: Callable[[], list[Path]] | list[Path] | None = None):
        self.locais = locais
        self._descobrir = _fontes_das_bases if fontes is None else fontes
        self._fontes: list[Path] = []
        self._conexoes: list[sqlite3.Connection] = []
        self._conferido = 0.0
        self._reconectar()

    def _reconectar(self) -> None:
        fontes = self._descobrir() if callable(self._descobrir) else list(self._descobrir)
        self._conferido = time.monotonic()
        if fontes == self._fontes:
            return
        for c in self._conexoes:
            c.close()
        # Só leitura; check_same_thread=False porque o monitor cria o banco numa
        # thread e analisa noutra. Ler em paralelo é seguro no SQLite.
        self._conexoes = [sqlite3.connect(f"file:{f}?mode=ro", uri=True, check_same_thread=False)
                          for f in fontes]
        self._fontes = fontes

    def get(self, sha256: str) -> str | None:
        if sha256 in self.locais:
            return self.locais[sha256]
        if time.monotonic() - self._conferido > RECONFERIR_BASES:
            self._reconectar()   # o link `atual` de uma base pode ter mudado
        for conexao in self._conexoes:
            try:
                linha = conexao.execute("SELECT nome FROM hashes WHERE sha256 = ?", (sha256,)).fetchone()
            except sqlite3.Error:
                continue   # base corrompida não derruba as outras
            if linha:
                return linha[0]
        return None

    def __contains__(self, sha256: str) -> bool:
        return self.get(sha256) is not None

    def __len__(self) -> int:
        total = len(self.locais)
        for conexao in self._conexoes:
            try:
                total += conexao.execute("SELECT count(*) FROM hashes").fetchone()[0]
            except sqlite3.Error:
                pass
        return total


def carregar(caminho: Path = ARQUIVO_PADRAO) -> Banco:
    return Banco(ler_txt(caminho))
