"""Gera os protótipos do Painel (muralha e mesa de guerra) nos quatro estados.
Cada estado vira um quadro próprio no canvas; a lógica é a mesma para os dois temas."""
import sys, pathlib

base = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('.')
anim = base / 'anim'
logica = (anim / 'painel_logica.js').read_text()


def pedra(cores, junta):
    """Azulejo de pedras desencontradas (240x120, duas fileiras), como data URI."""
    tij = [(0, 0, 118), (120, 0, 118), (-60, 60, 118), (60, 60, 118), (180, 60, 118)]
    rects = ''.join(f"<rect x='{x+1.5}' y='{y+1.5}' width='{w-3}' height='57' rx='5' fill='{c}'/>"
                    for (x, y, w), c in zip(tij, cores))
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='240' height='120'><rect width='240' height='120' fill='{junta}'/>{rects}</svg>"
    return 'url("data:image/svg+xml,' + svg.replace('#', '%23').replace('<', '%3C').replace('>', '%3E') + '")'


# pedra iluminada pela lua (azulada)
PEDRA_LUA = pedra(['#3c445a', '#353c50', '#414a62', '#333a4d', '#3a4258'], '#171c28')

temas = {'muralha': ('muralha_modelo.html', {'%%PEDRA%%': PEDRA_LUA})}
if (anim / 'mesa_modelo.html').exists():
    temas['mesa'] = ('mesa_modelo.html', {})

for tema, (arq, extra) in temas.items():
    modelo = (anim / arq).read_text().replace('%%LOGICA%%', logica.rstrip())
    for k, v in extra.items():
        modelo = modelo.replace(k, v)
    estados = ['repouso', 'varrendo', 'ameaca', 'atencao'] + (['cacada', 'parcial', 'protetor'] if tema == 'muralha' else [])
    for estado in estados:
        out = base / f'canvas/project/Painel-{tema}-{estado}.dc.html'
        out.write_text(modelo.replace('%%ESTADO%%', estado))
        print('ok', out.name)
