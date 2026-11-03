"""Heurísticas: detectar arquivos suspeitos sem precisar de assinatura."""

import math
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LIMIAR_SUSPEITO = 50              # pontuação a partir da qual o arquivo é "suspeito"
BYTES_AMOSTRA = 1024 * 1024       # entropia calculada no primeiro 1 MB

# Assinaturas de início de arquivo ("magic bytes")
MAGIC = {
    b"\x7fELF": "ELF",            # executável Linux
    b"MZ": "PE",                  # executável Windows
    b"#!": "script",              # script com shebang
}

EXT_EXECUTAVEIS = {".exe", ".sh", ".bat", ".cmd", ".scr", ".run", ".appimage", ".desktop", ".elf", ".bin"}
EXT_INOFENSIVAS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".txt", ".mp3", ".mp4", ".doc", ".docx", ".odt"}


@dataclass
class Sinais:
    entropia: float               # 0.0 (repetitivo) até 8.0 (parece aleatório)
    tipo_real: str | None         # "ELF", "PE", "script" ou None, pelo conteúdo
    executavel: bool              # tem permissão de execução no sistema
    oculto: bool                  # nome começa com "."
    extensao_dupla: bool          # ex.: "fatura.pdf.sh"
    disfarce: bool                # extensão inofensiva, mas conteúdo executável


def entropia_shannon(dados: bytes) -> float:
    if not dados:
        return 0.0
    total = len(dados)
    return -sum((n / total) * math.log2(n / total) for n in Counter(dados).values())


def detectar_tipo(cabecalho: bytes) -> str | None:
    for magic, tipo in MAGIC.items():
        if cabecalho.startswith(magic):
            return tipo
    return None


def coletar_sinais(caminho: Path) -> Sinais:
    with caminho.open("rb") as f:
        amostra = f.read(BYTES_AMOSTRA)

    tipo = detectar_tipo(amostra[:4])
    sufixos = [s.lower() for s in caminho.suffixes]
    ext = sufixos[-1] if sufixos else ""

    return Sinais(
        entropia=entropia_shannon(amostra),
        tipo_real=tipo,
        executavel=os.access(caminho, os.X_OK),
        oculto=caminho.name.startswith("."),
        extensao_dupla=len(sufixos) >= 2 and sufixos[-2] in EXT_INOFENSIVAS and ext in EXT_EXECUTAVEIS,
        disfarce=ext in EXT_INOFENSIVAS and tipo is not None,
    )


def avaliar_suspeita(s: Sinais) -> tuple[int, list[str]]:
    """Transforma os sinais numa pontuação de 0 a 100 e explica o porquê.

    Retorna (pontuacao, motivos), ex.: (70, ["executável disfarçado de .jpg"]).
    A partir de LIMIAR_SUSPEITO (50) o arquivo é marcado como suspeito.
    """
    pontuacao = 0
    motivos: list[str] = []

    # Quase nunca tem motivo legítimo: sozinhos já bastam para ser suspeito.
    if s.disfarce:
        pontuacao += 60
        motivos.append(f"conteúdo {s.tipo_real} disfarçado com extensão de arquivo comum")
    if s.extensao_dupla:
        pontuacao += 50
        motivos.append("extensão dupla (ex.: .pdf.sh)")

    # Sinais fracos sozinhos (dotfiles, zips e vídeos são normais),
    # mas que somam quando aparecem junto de um executável.
    if s.oculto and s.executavel:
        pontuacao += 30
        motivos.append("executável escondido (nome começa com '.')")
    if s.entropia > 7.2 and s.tipo_real in ("ELF", "PE"):
        pontuacao += 30
        motivos.append(f"executável com entropia alta ({s.entropia:.1f}): possível empacotamento ou ofuscação")

    return min(pontuacao, 100), motivos
