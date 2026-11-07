S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/anim/cav-anim.svg').read()
shared=open(S+'/cav/shared.svg').read()
CSS='''
.cv-corpo,.cv-pluma,.cv-brilho,.cv-selo{transform-box:view-box}
.cv-corpo{transform-origin:120px 300px}
.cv-pluma{transform-origin:124px 66px}
.cv-selo{opacity:0}
.cv-brilho{opacity:0}
.cv-card{transition:none}
/* parado e fora da vez: cinza */
.m-inativo .cv-retrato{filter:grayscale(1);opacity:.5}
/* agindo: respira, pluma balança, luz passa no elmo */
.m-agindo .cv-corpo{animation:cvRespira 3.2s ease-in-out infinite}
.m-agindo .cv-pluma{animation:cvPluma 2.6s ease-in-out infinite}
.m-agindo .cv-brilho{animation:cvBrilho 3.2s ease-in-out infinite}
.m-agindo{animation:cvMoldura 3.2s ease-in-out infinite}
/* entrada: repete a cada 4 s só para mostrar */
.m-entrada .cv-retrato{animation:cvAcorda 4s ease-out infinite}
.m-entrada .cv-corpo{animation:cvPasso 4s ease-out infinite}
.m-entrada .cv-selo{animation:cvSelo 4s ease-out infinite}
.m-entrada .cv-pluma{animation:cvPlumaEntra 4s ease-out infinite}
/* achou ameaça */
.m-achou .cv-corpo{animation:cvFirme 3s ease-out infinite}
.m-achou .cv-selo{fill:#ff8a7a;animation:cvSelo 3s ease-out infinite}
.m-achou .cv-pluma{animation:cvPlumaEntra 3s ease-out infinite}
.m-achou{animation:cvVermelho 3s ease-out infinite}
@keyframes cvRespira{0%,100%{transform:scale(1,1)}50%{transform:scale(1.008,1.016)}}
@keyframes cvPluma{0%,100%{transform:rotate(-2.5deg)}50%{transform:rotate(4deg)}}
@keyframes cvBrilho{0%,40%{opacity:0;transform:skewX(-18deg) translateX(0)}45%{opacity:1}70%{opacity:1;transform:skewX(-18deg) translateX(110px)}75%,100%{opacity:0;transform:skewX(-18deg) translateX(110px)}}
@keyframes cvMoldura{0%,100%{box-shadow:0 0 0 0 rgba(212,175,106,0)}50%{box-shadow:0 0 22px 2px rgba(212,175,106,.35)}}
@keyframes cvAcorda{0%{filter:grayscale(1);opacity:.5}12%{filter:grayscale(0) brightness(1.25);opacity:1}25%,100%{filter:none;opacity:1}}
@keyframes cvPasso{0%{transform:translateY(4px)}14%{transform:translateY(-3px)}24%,100%{transform:translateY(0)}}
@keyframes cvSelo{0%,6%{opacity:0}14%{opacity:.95}30%,100%{opacity:0}}
@keyframes cvPlumaEntra{0%{transform:rotate(0)}12%{transform:rotate(8deg)}22%{transform:rotate(-4deg)}32%,100%{transform:rotate(0)}}
@keyframes cvFirme{0%,100%{transform:translateY(0) scale(1)}10%{transform:translateY(-4px) scale(1.012)}22%{transform:translateY(0) scale(1)}}
@keyframes cvVermelho{0%,100%{box-shadow:0 0 0 0 rgba(255,138,122,0)}10%{box-shadow:0 0 26px 4px rgba(255,138,122,.55)}40%{box-shadow:0 0 0 0 rgba(255,138,122,0)}}
@media (prefers-reduced-motion: reduce){.cv-demo *,.cv-demo .cv-card{animation:none !important}}
'''
cards=[
 ('m-inativo','#2A3A60','1px','Fora da vez','Parado, cinza e apagado. É como ficam os personagens que não estão agindo.'),
 ('m-entrada','#D4AF6A','2px','Entrada · quando chega a vez dele','Meio segundo: ganha cor, dá um passo à frente, a pluma balança e o selo do peito acende. Aqui repete a cada 4 s só para mostrar.'),
 ('m-agindo','#D4AF6A','2px','Agindo · durante a varredura','Respira devagar, a pluma balança no vento e uma luz passa pelo elmo, como se conferisse cada arquivo. A moldura pulsa junto. Repete enquanto ele estiver trabalhando.'),
 ('m-achou','#FF8A7A','2px','Achou uma ameaça','Firma a postura de uma vez, o selo acende em vermelho e a moldura brilha vermelho. Depois a vez passa para o Carcereiro.'),
]
html=''
for cls,bor,bw,tit,desc in cards:
    html+=('<div style="display:flex;flex-direction:column;gap:12px;min-width:0">'
      '<div class="cv-card %s" style="background:#14203A;border:%s solid %s;border-radius:16px;padding:16px;display:flex;justify-content:center">'
      '<div class="cv-retrato" style="width:100%%;max-width:220px">%s</div></div>'
      '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-family:\'Fraunces\',Georgia,serif;font-size:18px;font-weight:600">%s</span>'
      '<span style="font-size:14px;color:#B7BCCB;line-height:1.5">%s</span></div></div>')%(cls,bw,bor,svg,tit,desc)
corpo=('<div class="cv-demo" style="width:1280px;box-sizing:border-box;padding:40px;background:#0D1626;color:#F3EEE2;font-family:\'Source Sans 3\',system-ui,sans-serif;display:flex;flex-direction:column;gap:28px">'
 '<header style="display:flex;flex-direction:column;gap:4px"><span style="font-size:13px;font-weight:600;letter-spacing:0.08em;color:#E3C384">ANIMAÇÕES · PROTÓTIPO 1</span>'
 '<span style="font-family:\'Fraunces\',Georgia,serif;font-size:30px;font-weight:600">O Cavaleiro em ação</span>'
 '<span style="font-size:15px;color:#B7BCCB;max-width:900px">Duas camadas: uma entrada curta quando chega a vez dele e um ciclo que se repete enquanto trabalha, seja a varredura curta ou longa. Movimentos pequenos para não aparecer peça solta. Com “reduzir movimento” ligado no sistema, fica só o destaque da moldura.</span></header>'
 '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px">'+html+'</div></div>')
fonts='<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&amp;family=Source+Code+Pro:wght@400;500&amp;family=Source+Sans+3:wght@400;500;600&amp;display=swap" rel="stylesheet">'
open(S+'/cav/cav-anim.html','w').write('<!doctype html><html><head><meta charset="utf-8">'+fonts+'<style>body{margin:0;background:#0D1626}'+CSS+'</style></head><body>'+shared+corpo+'</body></html>')
dc=('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<title>Cavaleiro em ação · animação</title>\n<script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n'+fonts+'\n<style>body{margin:0}'+CSS+'</style>\n</helmet>\n'
 +shared+'\n'+corpo+'\n</x-dc>\n<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":1280,"height":760}}\'>\nclass Component extends DCLogic {\n  renderVals() { return {}; }\n}\n</script>\n</body>\n</html>\n')
open(S+'/canvas/project/Anim-cavaleiro.dc.html','w').write(dc)
print('ok', '{{' in dc)
