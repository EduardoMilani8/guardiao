"""Monta a Quarentena-na-cela: pega o Carcereiro do retrato aprovado (car.svg),
tira a moldura, a parede e a porta do fundo, e deixa só a figura para ele
"espiar" por trás das grades. Os IDs viram cq* para não colidir com o Retrato."""
import re, sys, pathlib

base = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('.')
car = (base / 'cav/car.svg').read_text()
modelo = (base / 'anim/cela_modelo.html').read_text()

defs = car[car.index('<defs>'):car.index('</defs>') + len('</defs>')]
ini = car.index('<use href="#jvParts" stroke="#16121a" stroke-width="3.4">')
fim = car.index('<use href="#gFrame">')
corpo = car[ini:fim].rstrip()
assert corpo.endswith('</g>')  # fecha o <g clip-path=gArch>, que não vem junto
corpo = corpo[:-len('</g>')]

svg = ('<svg viewBox="0 0 240 300" width="100%" style="display: block">'
       + defs + corpo + '</svg>')
svg = re.sub(r'\bjv([A-Z0-9])', r'cq\1', svg)
saida = modelo.replace('%%CARCEREIRO%%', svg)
# cheia = a cela aprovada; vazia = primeiro uso; confirmar = pergunta antes do Apagar
for estado, nome in [('cheia', 'Clima2-quarentena'), ('vazia', 'Quarentena-vazia'), ('confirmar', 'Quarentena-apagar')]:
    (base / f'canvas/project/{nome}.dc.html').write_text(saida.replace('%%ESTADO%%', estado))
    print('ok', nome)
