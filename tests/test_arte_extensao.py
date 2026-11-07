import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "extensao"))
import construir_arte  # noqa: E402


def referencias_resolvidas(svg: str) -> bool:
    ET.fromstring(svg)   # XML válido
    ids = set(re.findall(r'\sid="([^"]+)"', svg))
    usados = set(re.findall(r'href="#([^"]+)"', svg)) | set(re.findall(r'url\(#([^)]+)\)', svg))
    return usados <= ids


def test_retratos_sozinhos():
    for nome in ("cavaleiro", "arqueira", "vidente", "carcereiro"):
        svg = construir_arte.retrato(nome)
        assert 'width="240"' in svg and referencias_resolvidas(svg), nome


def test_escudos_da_barra():
    escudos = construir_arte.escudos()
    assert set(escudos) == {"escudo-certo", "escudo-atencao", "escudo-ameaca",
                            *(f"escudo-procurando-{n}" for n in range(1, 5))}
    for svg in escudos.values():
        assert "currentColor" not in svg and referencias_resolvidas(svg)
