S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/anim/car-anim.svg').read()
shared=open(S+'/cav/shared.svg').read()
CSS='''
.car-corpo,.car-correntes,.car-grade{transform-box:view-box}
.car-chama,.car-luz,.car-luz2{transform-box:fill-box;transform-origin:center}
.car-chama{transform-origin:50% 100%}
.car-corpo{transform-origin:120px 300px}
.car-correntes{transform-origin:207px 36px}
.car-grade{transform:translateY(-280px)}
.m-inativo .car-retrato{filter:grayscale(1);opacity:.5}
/* entrada */
.m-entrada .car-retrato{animation:crAcorda 4s ease-out infinite}
.m-entrada .car-corpo{animation:crPasso 4s ease-out infinite}
.m-entrada .car-parede{animation:crClarao 4s ease-out infinite}
.m-entrada .car-chama{animation:crChamaSobe 4s ease-out infinite}
/* agindo: a lanterna tremula e a luz dança na parede, as correntes balançam */
.m-agindo{animation:crMoldura 3.2s ease-in-out infinite}
.m-agindo .car-corpo{animation:crRespira 3.2s ease-in-out infinite}
.m-agindo .car-chama{animation:crChama 1.3s ease-in-out infinite}
.m-agindo .car-luz{animation:crLuz 1.7s ease-in-out infinite}
.m-agindo .car-luz2{animation:crLuz 1.3s ease-in-out .2s infinite}
.m-agindo .car-parede{animation:crParede 2.3s ease-in-out infinite}
.m-agindo .car-correntes{animation:crBalanca 3.6s ease-in-out infinite}
/* trancou: a grade desce na porta atrás dele com um baque */
.m-trancou{animation:crVerde 4s ease-out infinite}
.cr-selo{position:absolute;left:50%;bottom:6px;transform:translate(-50%,0);opacity:0}
.m-trancou .cr-selo{animation:crSeloEntra 4s ease-out infinite}
.m-trancou .car-grade{animation:crGrade 4s infinite}
.m-trancou .car-corpo{animation:crBaque 4s ease-out infinite}
.m-trancou .car-correntes{animation:crSacode 4s ease-out infinite}
.m-trancou .car-parede{animation:crClaraoT 4s ease-out infinite}
.m-trancou .car-chama{animation:crChama 1.3s ease-in-out infinite}
@keyframes crRespira{0%,100%{transform:scale(1,1)}50%{transform:scale(1.008,1.016)}}
@keyframes crMoldura{0%,100%{box-shadow:0 0 0 0 rgba(212,175,106,0)}50%{box-shadow:0 0 22px 2px rgba(212,175,106,.35)}}
@keyframes crAcorda{0%{filter:grayscale(1);opacity:.5}12%{filter:grayscale(0) brightness(1.25);opacity:1}25%,100%{filter:none;opacity:1}}
@keyframes crPasso{0%{transform:translateY(4px)}14%{transform:translateY(-3px)}24%,100%{transform:translateY(0)}}
@keyframes crClarao{0%,6%{opacity:0}14%{opacity:.3}34%,100%{opacity:0}}
@keyframes crChamaSobe{0%,6%{transform:scale(1)}14%{transform:scale(1.5,1.9)}34%,100%{transform:scale(1)}}
@keyframes crChama{0%,100%{transform:scale(1,1)}25%{transform:scale(.85,1.2) skewX(4deg)}50%{transform:scale(1.1,.9)}75%{transform:scale(.9,1.15) skewX(-4deg)}}
@keyframes crLuz{0%,100%{opacity:.18;transform:scale(1)}40%{opacity:.3;transform:scale(1.08)}70%{opacity:.14;transform:scale(.96)}}
@keyframes crParede{0%,100%{opacity:.02}30%{opacity:.1}55%{opacity:.04}80%{opacity:.12}}
@keyframes crBalanca{0%,100%{transform:rotate(-1.6deg)}50%{transform:rotate(1.8deg)}}
@keyframes crVerde{0%,15%{border-color:#D4AF6A;box-shadow:0 0 0 0 rgba(143,211,176,0)}19%{border-color:#8FD3B0;box-shadow:0 0 0 3px rgba(143,211,176,.35),0 0 30px 6px rgba(143,211,176,.55)}45%,86%{border-color:#8FD3B0;box-shadow:0 0 0 3px rgba(143,211,176,.25),0 0 14px 2px rgba(143,211,176,.25)}96%,100%{border-color:#D4AF6A;box-shadow:0 0 0 0 rgba(143,211,176,0)}}
@keyframes crSeloEntra{0%,17%{opacity:0;transform:translate(-50%,10px) scale(.6)}23%{opacity:1;transform:translate(-50%,0) scale(1.12)}28%,86%{opacity:1;transform:translate(-50%,0) scale(1)}94%,100%{opacity:0;transform:translate(-50%,0) scale(1)}}
@keyframes crOuro{0%,12%{box-shadow:0 0 0 0 rgba(212,175,106,0)}20%{box-shadow:0 0 28px 5px rgba(212,175,106,.6)}50%,100%{box-shadow:0 0 0 0 rgba(212,175,106,0)}}
@keyframes crGrade{0%,4%{transform:translateY(-280px);opacity:1;animation-timing-function:cubic-bezier(.55,0,1,.45)}16%{transform:translateY(0);animation-timing-function:ease-out}19%{transform:translateY(-7px);animation-timing-function:ease-in}22%,86%{transform:translateY(0);opacity:1}96%,100%{transform:translateY(0);opacity:0}}
@keyframes crBaque{0%,15%{transform:translateY(0)}17%{transform:translateY(2px) scale(1.01,.99)}21%{transform:translateY(-2px)}26%,100%{transform:translateY(0)}}
@keyframes crSacode{0%,15%{transform:rotate(0)}18%{transform:rotate(4deg)}23%{transform:rotate(-3deg)}29%{transform:rotate(1.5deg)}36%,100%{transform:rotate(0)}}
@keyframes crClaraoT{0%,15%{opacity:0}18%{opacity:.22}40%,100%{opacity:.04}}
@media (prefers-reduced-motion: reduce){.car-demo *,.car-demo .car-card{animation:none !important}}
'''
cards=[
 ('m-inativo','#2A3A60','1px','Fora da vez','Parado, cinza e apagado. Durante a varredura ele fica assim: só entra quando aparece algo para trancar.'),
 ('m-entrada','#D4AF6A','2px','Entrada · quando acham uma ameaça','Ganha cor, dá um passo à frente e a chama da lanterna sobe, clareando a parede. Aqui repete a cada 4 s só para mostrar.'),
 ('m-agindo','#D4AF6A','2px','Agindo · aguardando sua ordem','Respira devagar. A chama da lanterna tremula, a luz dança nas pedras e as correntes balançam de leve. Fica assim até você decidir.'),
 ('m-trancou','#D4AF6A','2px','Trancou · quando você manda','A grade de ferro desce na porta escura atrás dele, com um baque: ele e as correntes sacodem e a lanterna clareia. A moldura passa para o verde de “tudo certo” e aparece o selo Trancado: o arquivo está preso.'),
]
html=''
SELO=('<div class="cr-selo" aria-hidden="true" style="display:flex;align-items:center;gap:6px;padding:4px 12px 4px 9px;border-radius:999px;background:#14203A;border:2px solid #8FD3B0;color:#8FD3B0;font-size:13px;font-weight:700;letter-spacing:.06em;white-space:nowrap">'
 '<svg width="14" height="14" viewBox="0 0 16 16"><path d="M4.5 7 V5 a3.5 3.5 0 0 1 7 0 V7" fill="none" stroke="currentColor" stroke-width="1.8"></path><rect x="2.5" y="7" width="11" height="8" rx="1.6" fill="currentColor"></rect></svg>TRANCADO</div>')
for cls,bor,bw,tit,desc in cards:
    selo = SELO if cls=='m-trancou' else ''
    html+=('<div style="display:flex;flex-direction:column;gap:12px;min-width:0">'
      '<div class="car-card '+cls+'" style="background:#14203A;border:'+bw+' solid '+bor+';border-radius:16px;padding:16px;display:flex;justify-content:center;position:relative">'
      '<div class="car-retrato" style="width:100%;max-width:220px">'+svg+'</div>'+selo+'</div>'
      '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-family:\'Fraunces\',Georgia,serif;font-size:18px;font-weight:600">'+tit+'</span>'
      '<span style="font-size:14px;color:#B7BCCB;line-height:1.5">'+desc+'</span></div></div>')
corpo=('<div class="car-demo" style="width:1280px;box-sizing:border-box;padding:40px;background:#0D1626;color:#F3EEE2;font-family:\'Source Sans 3\',system-ui,sans-serif;display:flex;flex-direction:column;gap:28px">'
 '<header style="display:flex;flex-direction:column;gap:4px"><span style="font-size:13px;font-weight:600;letter-spacing:0.08em;color:#E3C384">ANIMAÇÕES · PROTÓTIPO 4</span>'
 '<span style="font-family:\'Fraunces\',Georgia,serif;font-size:30px;font-weight:600">O Carcereiro em ação</span>'
 '<span style="font-size:15px;color:#B7BCCB;max-width:900px">Ele não procura ameaças: entra quando os outros acham algo e espera sua ordem. O gesto dele é a lanterna e as correntes; quando você manda trancar, a grade do calabouço desce atrás dele.</span></header>'
 '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px">'+html+'</div></div>')
fonts='<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&amp;family=Source+Code+Pro:wght@400;500&amp;family=Source+Sans+3:wght@400;500;600&amp;display=swap" rel="stylesheet">'
open(S+'/cav/car-anim.html','w').write('<!doctype html><html><head><meta charset="utf-8">'+fonts+'<style>body{margin:0;background:#0D1626}'+CSS+'</style></head><body>'+shared+corpo+'</body></html>')
dc=('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<title>Carcereiro em ação · animação</title>\n<script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n'+fonts+'\n<style>body{margin:0}'+CSS+'</style>\n</helmet>\n'
 +shared+'\n'+corpo+'\n</x-dc>\n<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":1280,"height":760}}\'>\nclass Component extends DCLogic {\n  renderVals() { return {}; }\n}\n</script>\n</body>\n</html>\n')
open(S+'/canvas/project/Anim-carcereiro.dc.html','w').write(dc)
print('ok','{{' in dc)
