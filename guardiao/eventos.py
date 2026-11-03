"""Converte resultados do motor em eventos simples (dicts prontos para JSON).

É a ponte entre a detecção e qualquer interface: a CLI imprime, o launcher
anima personagens, e nenhum dos dois precisa conhecer o scanner por dentro.
"""

from pathlib import Path

from .scanner import Resultado


def de_resultado(r: Resultado, raiz: Path) -> dict:
    if r.infectado:
        veredito = "ameaca"
    elif r.suspeito:
        veredito = "suspeito"
    else:
        veredito = "limpo"
    return {
        "tipo": "arquivo",
        "nome": r.caminho.name,
        "caminho": str(r.caminho.relative_to(raiz)) if r.caminho.is_relative_to(raiz) else str(r.caminho),
        "veredito": veredito,
        "camada": r.camada if veredito != "limpo" else None,
        "ameaca": r.ameaca,
        "pontuacao": r.pontuacao,
        "motivos": r.motivos,
    }


def de_erro(caminho: Path, erro: OSError, raiz: Path) -> dict:
    return {
        "tipo": "erro",
        "caminho": str(caminho.relative_to(raiz)) if caminho.is_relative_to(raiz) else str(caminho),
        "mensagem": erro.strerror or str(erro),
    }
