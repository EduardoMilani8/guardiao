"""Os arquivos dos serviços do systemd em contrib/."""

import configparser
from pathlib import Path

CONTRIB = Path(__file__).resolve().parent.parent / "contrib"


def servico(nome: str) -> configparser.SectionProxy:
    leitor = configparser.ConfigParser(strict=False, interpolation=None)
    leitor.optionxform = str
    leitor.read(CONTRIB / nome)
    return leitor["Service"]


def tamanho(valor: str) -> int:
    multiplicador = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}
    return int(valor[:-1]) * multiplicador[valor[-1]] if valor[-1] in multiplicador else int(valor)


def test_varreduras_automaticas_nunca_derrubam_um_jogo():
    # 08/11/2026: a completa de domingo somou ~2 GB e o kernel, sem memória,
    # matou o jogo que estava aberto. Com teto, ela anda devagar; se mesmo
    # assim faltar memória, quem morre é ela.
    for nome in ("guarnicao-varrer-rapida.service", "guarnicao-varrer-completa.service"):
        s = servico(nome)
        assert tamanho(s["MemoryHigh"]) < tamanho(s["MemoryMax"]) <= 3 << 30, nome
        assert tamanho(s["MemorySwapMax"]) <= 1 << 30, nome   # não enche a swap do jogo
        assert int(s["OOMScoreAdjust"]) == 1000, nome         # a primeira a sair
