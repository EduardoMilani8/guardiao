S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/anim/arq-anim.svg').read()
shared=open(S+'/cav/shared.svg').read()
CSS='''
.ar-corpo,.ar-selo,.ar-sobr,.ar-palp{transform-box:view-box}
.ar-olhos,.ar-folha,.ar-flecha{transform-box:fill-box;transform-origin:center}
.ar-corpo{transform-origin:120px 300px}
.ar-selo,.ar-folha,.ar-flecha{opacity:0}
.ar-onda{stroke-dasharray:80 400;stroke-dashoffset:80;opacity:0}
.m-agindo .ar-onda{animation:arOnda 4.8s ease-in-out infinite}
.m-inativo .ar-retrato{filter:grayscale(1);opacity:.5}
/* entrada */
.m-entrada .ar-retrato{animation:arAcorda 4s ease-out infinite}
.m-entrada .ar-corpo{animation:arPasso 4s ease-out infinite}
.m-entrada .ar-selo{animation:arSelo 4s ease-out infinite}
/* agindo: respira, o vento passa com folhas e ela aperta os olhos para ver longe */
.m-agindo{animation:arMoldura 3.2s ease-in-out infinite}
.m-agindo .ar-corpo{animation:arRespira 3.2s ease-in-out infinite}
.m-agindo .ar-folha{animation:arFolha 4.8s ease-in-out infinite}
.m-agindo .ar-olhos{animation:arOlhos 4.8s ease-in-out infinite}
.m-agindo .ar-palp{animation:arPalp 4.8s ease-in-out infinite}
.m-agindo .ar-sobr{animation:arSobr 4.8s ease-in-out infinite}
/* achou: saraivada de flechas saindo de trás dela para a frente */
.m-achou{animation:arVermelho 3s ease-out infinite}
.m-achou .ar-corpo{animation:arFirme 3s ease-out infinite}
.m-achou .ar-selo{fill:#ff8a7a;animation:arSelo 3s ease-out infinite}
.m-achou .ar-flecha{animation:arFlecha 3s ease-in infinite}
.m-achou .ar-olhos{animation:arOlhosFixo 3s ease-out infinite}
.m-achou .ar-palp{animation:arPalpFixo 3s ease-out infinite}
.m-achou .ar-sobr{animation:arSobrFixo 3s ease-out infinite}
@keyframes arRespira{0%,100%{transform:scale(1,1)}50%{transform:scale(1.008,1.016)}}
@keyframes arMoldura{0%,100%{box-shadow:0 0 0 0 rgba(212,175,106,0)}50%{box-shadow:0 0 22px 2px rgba(212,175,106,.35)}}
@keyframes arAcorda{0%{filter:grayscale(1);opacity:.5}12%{filter:grayscale(0) brightness(1.25);opacity:1}25%,100%{filter:none;opacity:1}}
@keyframes arPasso{0%{transform:translateY(4px)}14%{transform:translateY(-3px)}24%,100%{transform:translateY(0)}}
@keyframes arSelo{0%,6%{opacity:0}14%{opacity:.95}30%,100%{opacity:0}}
@keyframes arFolha{0%{opacity:0;transform:translate(-10px,0) rotate(0)}4%{opacity:1}14%{transform:translate(70px,-8px) rotate(160deg)}24%{transform:translate(150px,6px) rotate(330deg)}34%{opacity:1;transform:translate(240px,-6px) rotate(520deg)}36%,100%{opacity:0;transform:translate(260px,-6px) rotate(540deg)}}
@keyframes arOnda{0%{opacity:0;stroke-dashoffset:80}3%{opacity:1}30%{opacity:1;stroke-dashoffset:-260}36%,100%{opacity:0;stroke-dashoffset:-300}}
@keyframes arOlhos{0%,16%{transform:scaleY(1)}24%,46%{transform:scaleY(.62)}54%,100%{transform:scaleY(1)}}
@keyframes arPalp{0%,16%{transform:translateY(0)}24%,46%{transform:translateY(1.1px)}54%,100%{transform:translateY(0)}}
@keyframes arSobr{0%,16%{transform:translateY(0)}24%,46%{transform:translateY(1.3px)}54%,100%{transform:translateY(0)}}
@keyframes arVermelho{0%,100%{box-shadow:0 0 0 0 rgba(255,138,122,0)}10%{box-shadow:0 0 26px 4px rgba(255,138,122,.55)}40%{box-shadow:0 0 0 0 rgba(255,138,122,0)}}
@keyframes arFirme{0%,100%{transform:translateY(0) scale(1)}10%{transform:translateY(-4px) scale(1.012)}22%{transform:translateY(0) scale(1)}}
@keyframes arFlecha{0%{opacity:0;transform:translateX(0) scale(.35)}6%{opacity:1}42%{opacity:1;transform:translateX(150px) scale(2.6)}48%,100%{opacity:0;transform:translateX(170px) scale(2.8)}}
@keyframes arOlhosFixo{0%{transform:scaleY(1)}8%,60%{transform:scaleY(.62)}70%,100%{transform:scaleY(1)}}
@keyframes arPalpFixo{0%{transform:translateY(0)}8%,60%{transform:translateY(1.6px)}70%,100%{transform:translateY(0)}}
@keyframes arSobrFixo{0%{transform:translateY(0)}8%,60%{transform:translateY(1.6px)}70%,100%{transform:translateY(0)}}
@media (prefers-reduced-motion: reduce){.ar-demo *,.ar-demo .ar-card{animation:none !important}}
'''
cards=[
 ('m-inativo','#2A3A60','1px','Fora da vez','Parada, cinza e apagada, como todos que não estão agindo.'),
 ('m-entrada','#D4AF6A','2px','Entrada · quando chega a vez dela','Igual ao Cavaleiro: ganha cor, dá um passo à frente e o broche de folha acende. Aqui repete a cada 4 s só para mostrar.'),
 ('m-agindo','#D4AF6A','2px','Agindo · durante a varredura','Respira devagar. Uma rajada de vento passa em ondas, levando algumas folhas na frente dela, ela aperta os olhos como quem mira longe e logo volta ao normal. Repete enquanto ela trabalha.'),
 ('m-achou','#FF8A7A','2px','Achou uma ameaça','Uma saraivada de flechas sai de trás dela e voa para a frente, crescendo como se viesse na direção de quem olha. Ela firma a postura e mantém o olhar apertado, e a moldura brilha vermelho.'),
]
html=''
for cls,bor,bw,tit,desc in cards:
    html+=('<div style="display:flex;flex-direction:column;gap:12px;min-width:0">'
      '<div class="ar-card %s" style="background:#14203A;border:%s solid %s;border-radius:16px;padding:16px;display:flex;justify-content:center">'
      '<div class="ar-retrato" style="width:100%%;max-width:220px">%s</div></div>'
      '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-family:\'Fraunces\',Georgia,serif;font-size:18px;font-weight:600">%s</span>'
      '<span style="font-size:14px;color:#B7BCCB;line-height:1.5">%s</span></div></div>')%(cls,bw,bor,svg,tit,desc)
corpo=('<div class="ar-demo" style="width:1280px;box-sizing:border-box;padding:40px;background:#0D1626;color:#F3EEE2;font-family:\'Source Sans 3\',system-ui,sans-serif;display:flex;flex-direction:column;gap:28px">'
 '<header style="display:flex;flex-direction:column;gap:4px"><span style="font-size:13px;font-weight:600;letter-spacing:0.08em;color:#E3C384">ANIMAÇÕES · PROTÓTIPO 2</span>'
 '<span style="font-family:\'Fraunces\',Georgia,serif;font-size:30px;font-weight:600">A Arqueira em ação</span>'
 '<span style="font-size:15px;color:#B7BCCB;max-width:900px">Mesmo modelo do Cavaleiro: entrada curta quando chega a vez e um ciclo que se repete enquanto trabalha. O gesto dela é o vento com folhas e o olhar apertado de quem mira longe; quando acha uma ameaça, solta uma saraivada de flechas.</span></header>'
 '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px">'+html+'</div></div>')
fonts='<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&amp;family=Source+Code+Pro:wght@400;500&amp;family=Source+Sans+3:wght@400;500;600&amp;display=swap" rel="stylesheet">'
open(S+'/cav/arq-anim.html','w').write('<!doctype html><html><head><meta charset="utf-8">'+fonts+'<style>body{margin:0;background:#0D1626}'+CSS+'</style></head><body>'+shared+corpo+'</body></html>')
dc=('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<title>Arqueira em ação · animação</title>\n<script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n'+fonts+'\n<style>body{margin:0}'+CSS+'</style>\n</helmet>\n'
 +shared+'\n'+corpo+'\n</x-dc>\n<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":1280,"height":760}}\'>\nclass Component extends DCLogic {\n  renderVals() { return {}; }\n}\n</script>\n</body>\n</html>\n')
open(S+'/canvas/project/Anim-arqueira.dc.html','w').write(dc)
print('ok','{{' in dc)
