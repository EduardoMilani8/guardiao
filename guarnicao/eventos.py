"""Converte resultados do motor em eventos simples (dicts prontos para JSON).

É a ponte entre a detecção e qualquer interface: a CLI imprime, o launcher
anima personagens, e nenhum dos dois precisa conhecer o scanner por dentro.
"""

from pathlib import Path

from .scanner import Resultado


def relativo(caminho: Path | str, raiz: Path | None) -> str:
    """Caminho curto para mostrar: relativo à raiz, se houver uma só."""
    caminho = Path(caminho)
    return str(caminho.relative_to(raiz)) if raiz and caminho.is_relative_to(raiz) else str(caminho)


def de_resultado(r: Resultado, raiz: Path | None) -> dict:
    if r.infectado:
        veredito = "ameaca"
    elif r.suspeito:
        veredito = "suspeito"
    else:
        veredito = "limpo"
    return {
        "tipo": "arquivo",
        "nome": r.caminho.name,
        "caminho": relativo(r.caminho, raiz),
        "veredito": veredito,
        "camada": r.camada if veredito != "limpo" else None,
        "ameaca": r.ameaca,
        "pontuacao": r.pontuacao,
        "motivos": r.motivos,
    }

