"""Percorre arquivos e aplica as camadas de detecção."""

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from . import heuristicas

TAMANHO_BLOCO = 64 * 1024


@dataclass
class Resultado:
    caminho: Path
    sha256: str
    ameaca: str | None = None          # nome, se bateu com uma assinatura
    pontuacao: int = 0                 # 0-100, vindo das heurísticas
    motivos: list[str] = field(default_factory=list)

    @property
    def infectado(self) -> bool:
        return self.ameaca is not None

    @property
    def suspeito(self) -> bool:
        return not self.infectado and self.pontuacao >= heuristicas.LIMIAR_SUSPEITO


def calcular_sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        while bloco := f.read(TAMANHO_BLOCO):
            h.update(bloco)
    return h.hexdigest()


def listar_arquivos(alvo: Path) -> Iterator[Path]:
    """Arquivos regulares sob `alvo`, sem seguir links simbólicos."""
    if alvo.is_file():
        yield alvo
        return
    for raiz, _dirs, arquivos in os.walk(alvo, followlinks=False):
        for nome in arquivos:
            p = Path(raiz) / nome
            if p.is_file() and not p.is_symlink():
                yield p


def analisar(caminho: Path, banco: dict[str, str]) -> Resultado:
    sha = calcular_sha256(caminho)
    resultado = Resultado(caminho=caminho, sha256=sha, ameaca=banco.get(sha))
    if not resultado.infectado:
        sinais = heuristicas.coletar_sinais(caminho)
        resultado.pontuacao, resultado.motivos = heuristicas.avaliar_suspeita(sinais)
    return resultado


def varrer(alvo: Path, banco: dict[str, str]) -> Iterator[Resultado | tuple[Path, OSError]]:
    """Gera um Resultado por arquivo, ou (caminho, erro) se não deu pra ler."""
    for caminho in listar_arquivos(alvo):
        try:
            yield analisar(caminho, banco)
        except OSError as erro:
            yield caminho, erro
