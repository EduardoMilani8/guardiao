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
                            "escudo-atencao-menu", "escudo-ameaca-menu",
                            *(f"escudo-procurando-{n}" for n in range(1, 5))}
    for svg in escudos.values():
        assert "currentColor" not in svg and referencias_resolvidas(svg)


def test_css_sem_margem_negativa():
    # O St (toolkit da barra) não aceita margem negativa: o cartão ficava com
    # altura infinita e vazio na tela (achado no teste ao vivo, GNOME 50).
    import re
    css = (RAIZ / "extensao" / "guarnicao@eduardomilani8.github.io" / "stylesheet.css").read_text()
    assert not re.search(r"margin[^;]*:\s*[^;]*-\d", css)


def test_emblema_dos_avisos_curtos():
    # O emblema dourado do castelo, dos avisos curtos (limpa e trancado) do avisos-v3.
    svg = construir_arte.emblema()
    assert 'aria-label="Guarnição"' in svg and 'width="34"' in svg and referencias_resolvidas(svg)


def test_escudos_coloridos_do_menu():
    # Dentro do menu, a cor aparece junto do texto (barra-v2): âmbar e vermelho.
    escudos = construir_arte.escudos()
    assert "#F0B65A" in escudos["escudo-atencao-menu"] and "#FF8A7A" in escudos["escudo-ameaca-menu"]
