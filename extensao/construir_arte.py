"""Gera a arte da extensão a partir dos desenhos aprovados.

Rode de novo se os retratos (guarnicao/launcher/estatico/arte) ou o escudo
(design/telas/barra-v2.html) mudarem: python3 extensao/construir_arte.py
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARTE_PAINEL = RAIZ / "guarnicao" / "launcher" / "estatico" / "arte"
BARRA = RAIZ / "design" / "telas" / "barra-v2.html"
DESTINO = RAIZ / "extensao" / "guarnicao@eduardomilani8.github.io" / "arte"
NS = 'xmlns="http://www.w3.org/2000/svg"'
# A barra do GNOME é sempre escura e o texto dela é branco. Não usamos ícone
# "symbolic": o GNOME recolore preenchendo os traços, e o escudo vazado viraria
# um escudo cheio.
COR_DA_BARRA = "#ffffff"


def _interior(svg: str) -> str:
    return re.sub(r"^\s*<svg[^>]*>|</svg>\s*$", "", svg.strip())


def retrato(nome: str) -> str:
    """O retrato com as definições comuns (moldura etc.) dentro, para abrir sozinho."""
    proprio = (ARTE_PAINEL / f"{nome}.svg").read_text(encoding="utf-8").strip()
    abertura = re.match(r"<svg[^>]*>", proprio).group(0)
    viewbox = re.search(r'viewBox="([^"]+)"', abertura).group(1)
    comum = _interior((ARTE_PAINEL / "comum.svg").read_text(encoding="utf-8"))
    return (f'<svg {NS} xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="{viewbox}" '
            f'width="240" height="300">{comum}{proprio[len(abertura):]}')


def escudos() -> dict[str, str]:
    html = BARRA.read_text(encoding="utf-8")

    def pega(padrao: str) -> str:
        return re.search(padrao, html, flags=re.S).group(0)

    mascara = pega(r'<mask id="brMx".*?</mask>')
    simbolo = {i: re.sub(r"^<symbol[^>]*>|</symbol>$", "", pega(rf'<symbol id="{i}"[^>]*>.*?</symbol>'))
               for i in ("brOk", "brVar", "brAtn", "brAmc")}

    def svg(corpo: str, extra: str = "") -> str:
        return (f'<svg {NS} width="16" height="16" viewBox="0 0 16 16"><defs>{mascara}{extra}</defs>'
                f"{corpo}</svg>").replace("currentColor", COR_DA_BARRA)

    saida = {"escudo-certo": svg(simbolo["brOk"]), "escudo-atencao": svg(simbolo["brAtn"]),
             "escudo-ameaca": svg(simbolo["brAmc"])}
    for nivel in range(1, 5):
        # O escudo vai de y 2,5 a 14,5; enche de baixo para cima, em 4 passos.
        topo = 14.5 - 12 * nivel / 4
        recorte = f'<clipPath id="brMeio"><rect x="0" y="{topo:.2f}" width="16" height="16"/></clipPath>'
        saida[f"escudo-procurando-{nivel}"] = svg(simbolo["brVar"], recorte)
    return saida


def ameia(largura: int = 426) -> str:
    """A faixa de ameias do alto do aviso (avisos-v3): dentes de 18 px a cada 30 px."""
    dentes = "".join(f'<rect x="{x}" y="0" width="18" height="8" fill="#3a4258"/>' for x in range(6, largura, 30))
    return (f'<svg {NS} width="{largura}" height="16" viewBox="0 0 {largura} 16">'
            f'<rect x="0" y="7" width="{largura}" height="9" fill="#3a4258"/>{dentes}'
            f'<rect x="0" y="7" width="{largura}" height="1" fill="#5a6584"/></svg>')


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome in ("cavaleiro", "arqueira", "vidente", "carcereiro"):
        (DESTINO / f"{nome}.svg").write_text(retrato(nome), encoding="utf-8")
    for nome, svg in escudos().items():
        (DESTINO / f"{nome}.svg").write_text(svg, encoding="utf-8")
    (DESTINO / "ameia.svg").write_text(ameia(), encoding="utf-8")
    print(f"Arte gerada em {DESTINO}")


if __name__ == "__main__":
    main()
