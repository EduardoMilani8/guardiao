"""Percorre arquivos e aplica as camadas de detecção."""

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol

from . import compactados, heuristicas, regras_yara

TAMANHO_BLOCO = 64 * 1024

class BancoDeHashes(Protocol):
    """Um dict {sha256: nome} ou o assinaturas.Banco, que consulta o disco."""
    def get(self, sha256: str, /) -> str | None: ...


@dataclass
class Resultado:
    caminho: Path
    sha256: str
    ameaca: str | None = None          # nome, se bateu com uma assinatura
    pontuacao: int = 0                 # 0-100, vindo das heurísticas
    motivos: list[str] = field(default_factory=list)
    camada: str | None = None          # quem decidiu: "hash", "yara" ou "heuristica"

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


def analisar(caminho: Path, banco: BancoDeHashes, yara=None, clamav=None) -> Resultado:
    """Camadas em ordem de certeza: hash → ClamAV → YARA → heurísticas."""
    sha = calcular_sha256(caminho)
    resultado = Resultado(caminho=caminho, sha256=sha, ameaca=banco.get(sha))
    if resultado.infectado:
        resultado.camada = "hash"
        return resultado

    if clamav is not None:
        try:
            if nome := clamav.verificar(caminho):
                resultado.ameaca, resultado.camada = f"{nome} (ClamAV)", "clamav"
                return resultado
        except OSError as erro:
            # clamd reiniciando (ex.: carregando assinaturas novas): as outras camadas seguem.
            resultado.motivos.append(f"ClamAV não respondeu: {erro}")

    if yara is not None and not _e_arquivo_de_regras(caminho):
        for o in regras_yara.verificar(caminho, yara):
            if o.gravidade == "info":
                continue   # informativo: não pesa na suspeita
            resultado.camada = "yara"
            if o.gravidade == "alta":
                resultado.ameaca = f"{o.regra} (YARA)"
                return resultado
            resultado.pontuacao += regras_yara.PESO_MEDIA
            resultado.motivos.append(f"regra YARA {o.regra}: {o.descricao}")

    # ClamAV já abre pacotes sozinho; aqui o hash e o YARA olham dentro deles.
    if (exame := compactados.examinar(caminho, banco, yara)) is not None:
        if exame.ameaca:
            resultado.ameaca, resultado.camada = exame.ameaca, exame.camada
            return resultado
        if exame.pontuacao:
            resultado.camada = resultado.camada or exame.camada
            resultado.pontuacao += exame.pontuacao
            resultado.motivos += exame.motivos

    pontos, motivos = heuristicas.avaliar_suspeita(heuristicas.coletar_sinais(caminho))
    if pontos and resultado.camada is None:
        resultado.camada = "heuristica"
    resultado.pontuacao = min(resultado.pontuacao + pontos, 100)
    resultado.motivos += motivos
    return resultado


def _e_arquivo_de_regras(caminho: Path) -> bool:
    if not caminho.name.lower().endswith((".yar", ".yara")):
        return False
    with caminho.open("rb") as f:
        return regras_yara.e_arquivo_de_regras(caminho.name, f.read(TAMANHO_BLOCO))


def varrer(alvo: Path, banco: BancoDeHashes, yara=None, clamav=None) -> Iterator[Resultado | tuple[Path, OSError]]:
    """Gera um Resultado por arquivo, ou (caminho, erro) se não deu pra ler."""
    pasta_regras = regras_yara.PASTA_PADRAO.resolve()
    for caminho in listar_arquivos(alvo):
        # As próprias regras contêm os padrões que procuram: não se autodetectar.
        if caminho.resolve().is_relative_to(pasta_regras):
            continue
        try:
            yield analisar(caminho, banco, yara, clamav)
        except OSError as erro:
            yield caminho, erro
