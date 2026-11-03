"""Cache de arquivos já verificados e limpos, para a próxima varredura pulá-los.

Um arquivo só é pulado se nada mudou: mesmo inode, tamanho, mtime e ctime, e
mesma versão do motor (regras, assinaturas e heurísticas). O ctime importa
porque o mtime pode ser falsificado (`touch -d`), mas o ctime é o kernel quem
atualiza em qualquer mudança. Ameaças e suspeitos nunca entram no cache.

O cache é só um atalho: se o banco estiver ocupado (duas varreduras ao mesmo
tempo) ou corrompido, a varredura segue analisando tudo, nunca quebra.
"""

import hashlib
import inspect
import os
import sqlite3
from pathlib import Path

from . import __version__, assinaturas, bases, heuristicas, regras_yara, scanner

PADRAO = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "guardiao" / "cache.sqlite"


def versao_motor() -> str:
    """Muda sempre que algo que afeta o veredito muda; invalida o cache inteiro."""
    h = hashlib.sha256(__version__.encode())
    h.update(str(regras_yara.disponivel()).encode())
    for arquivo in sorted(regras_yara.PASTA_PADRAO.rglob("*.yar")):
        h.update(arquivo.read_bytes())
    h.update(assinaturas.ARQUIVO_PADRAO.read_bytes())
    h.update(bases.versoes_em_uso(bases.registradas()).encode())
    for modulo in (heuristicas, scanner):
        h.update(inspect.getsource(modulo).encode())
    return h.hexdigest()[:16]


class Cache:
    def __init__(self, caminho: Path | None = None, versao: str | None = None):
        caminho = caminho or PADRAO
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.versao = versao or versao_motor()
        self.db = sqlite3.connect(caminho, timeout=10)
        # WAL: quem lê não espera quem escreve, então duas varreduras convivem.
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS limpos ("
            " dev INTEGER, ino INTEGER, tamanho INTEGER, mtime INTEGER, ctime INTEGER, versao TEXT,"
            " PRIMARY KEY (dev, ino))"
        )
        self._pendentes = 0

    def limpo(self, st: os.stat_result) -> bool:
        try:
            linha = self.db.execute(
                "SELECT tamanho, mtime, ctime, versao FROM limpos WHERE dev = ? AND ino = ?",
                (st.st_dev, st.st_ino),
            ).fetchone()
        except sqlite3.Error:
            return False    # na dúvida, analisa
        return linha == (st.st_size, st.st_mtime_ns, st.st_ctime_ns, self.versao)

    def marcar_limpo(self, st: os.stat_result) -> None:
        self._escrever(
            "INSERT OR REPLACE INTO limpos VALUES (?, ?, ?, ?, ?, ?)",
            (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, self.versao),
        )

    def esquecer(self, st: os.stat_result) -> None:
        self._escrever("DELETE FROM limpos WHERE dev = ? AND ino = ?", (st.st_dev, st.st_ino))

    def _escrever(self, sql: str, valores: tuple) -> None:
        try:
            self.db.execute(sql, valores)
            self._pendentes += 1
            if self._pendentes >= 1000:    # gravar em lotes é muito mais rápido que um commit por arquivo
                self.salvar()
        except sqlite3.Error:
            pass    # perder uma entrada só faz o arquivo ser analisado de novo

    def salvar(self) -> None:
        try:
            self.db.commit()
        except sqlite3.Error:
            pass
        self._pendentes = 0

    def fechar(self) -> None:
        self.salvar()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()
