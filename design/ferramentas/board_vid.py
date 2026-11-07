S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/anim/vid-anim.svg').read()
shared=open(S+'/cav/shared.svg').read()
CSS='''
.vd-corpo,.vd-circulo{transform-box:view-box}
.vd-halo,.vd-halo2,.vd-fumo,.vd-faisca{transform-box:fill-box;transform-origin:center}
.vd-corpo{transform-origin:120px 300px}
.vd-circulo{transform-origin:120px 150px}
.vd-orbe,.vd-fumo,.vd-faisca{opacity:0}
.m-inativo .vd-retrato{filter:grayscale(1);opacity:.5}
/* entrada */
.m-entrada .vd-retrato{animation:vdAcorda 4s ease-out infinite}
.m-entrada .vd-corpo{animation:vdPasso 4s ease-out infinite}
.m-entrada .vd-orbe{animation:vdClarao 4s ease-out infinite}
/* agindo: o orbe pulsa, fumaça mágica e faíscas sobem do cajado, os olhos brilham */
.m-agindo{animation:vdMoldura 3.2s ease-in-out infinite}
.m-agindo .vd-corpo{animation:vdRespira 3.2s ease-in-out infinite}
.m-agindo .vd-halo{animation:vdHalo 2.4s ease-in-out infinite}
.m-agindo .vd-halo2{animation:vdHalo 2.4s ease-in-out .3s infinite}
.m-agindo .vd-orbe{animation:vdOrbe 2.4s ease-in-out infinite}
.m-agindo .vd-fumo{animation:vdFumo 2.1s ease-out infinite}
.m-agindo .vd-faisca{animation:vdFaisca 3.2s ease-out infinite}
.m-agindo .vd-olho{animation:vdOlho 2.4s ease-in-out infinite}
/* achou: o círculo mágico gira e fica vermelho */
.m-achou{animation:vdVermelho 3s ease-out infinite}
.m-achou .vd-corpo{animation:vdFirme 3s ease-out infinite}
.m-achou .vd-circulo{animation:vdGira 3s cubic-bezier(.2,.7,.3,1) infinite}
.m-achou .vd-circulo *{stroke:#ff8a7a}
.m-achou .vd-orbe{fill:#ffc2b8;animation:vdClarao 3s ease-out infinite}
.m-achou .vd-olho{fill:#ff8a7a;animation:vdOlhoFixo 3s ease-out infinite}
.m-achou .vd-halo,.m-achou .vd-halo2{fill:#ff8a7a}
@keyframes vdRespira{0%,100%{transform:scale(1,1)}50%{transform:scale(1.008,1.016)}}
@keyframes vdMoldura{0%,100%{box-shadow:0 0 0 0 rgba(212,175,106,0)}50%{box-shadow:0 0 22px 2px rgba(212,175,106,.35)}}
@keyframes vdAcorda{0%{filter:grayscale(1);opacity:.5}12%{filter:grayscale(0) brightness(1.25);opacity:1}25%,100%{filter:none;opacity:1}}
@keyframes vdPasso{0%{transform:translateY(4px)}14%{transform:translateY(-3px)}24%,100%{transform:translateY(0)}}
@keyframes vdClarao{0%,6%{opacity:0}14%{opacity:.95}34%,100%{opacity:0}}
@keyframes vdHalo{0%,100%{transform:scale(1);opacity:.2}50%{transform:scale(1.35);opacity:.45}}
@keyframes vdOrbe{0%,100%{opacity:0}50%{opacity:.55}}
@keyframes vdFumo{0%{opacity:0;transform:translateY(6px) scaleX(.6)}25%{opacity:.75}100%{opacity:0;transform:translateY(-14px) scaleX(1.3)}}
@keyframes vdFaisca{0%{opacity:0;transform:translate(0,0) scale(.4)}15%{opacity:1}60%{opacity:0;transform:translate(0,-34px) scale(1.2)}100%{opacity:0;transform:translate(0,-34px) scale(1.2)}}
@keyframes vdOlho{0%,100%{opacity:.35}50%{opacity:.85}}
@keyframes vdVermelho{0%,100%{box-shadow:0 0 0 0 rgba(255,138,122,0)}10%{box-shadow:0 0 26px 4px rgba(255,138,122,.55)}40%{box-shadow:0 0 0 0 rgba(255,138,122,0)}}
@keyframes vdFirme{0%,100%{transform:translateY(0) scale(1)}10%{transform:translateY(-4px) scale(1.012)}22%{transform:translateY(0) scale(1)}}
@keyframes vdGira{0%{transform:rotate(0)}60%,100%{transform:rotate(360deg)}}
@keyframes vdOlhoFixo{0%{opacity:.35}10%,70%{opacity:.9}100%{opacity:.35}}
@media (prefers-reduced-motion: reduce){.vd-demo *,.vd-demo .vd-card{animation:none !important}}
'''
cards=[
 ('m-inativo','#2A3A60','1px','Fora da vez','Parado, cinza e apagado, como todos que não estão agindo.'),
 ('m-entrada','#D4AF6A','2px','Entrada · quando chega a vez dele','Igual aos outros: ganha cor e dá um passo à frente. O orbe do cajado solta um clarão. Aqui repete a cada 4 s só para mostrar.'),
 ('m-agindo','#D4AF6A','2px','Agindo · durante a varredura','Respira devagar. O orbe do cajado pulsa, uma fumaça mágica sobe dele em espiral com algumas faíscas, e os olhos brilham junto. Repete enquanto ele trabalha.'),
 ('m-achou','#FF8A7A','2px','Achou uma ameaça','O círculo mágico atrás dele fica vermelho e dá uma volta inteira. O orbe e os olhos acendem em vermelho, ele firma a postura e a moldura brilha vermelho.'),
]
html=''
for cls,bor,bw,tit,desc in cards:
    html+=('<div style="display:flex;flex-direction:column;gap:12px;min-width:0">'
      '<div class="vd-card %s" style="background:#14203A;border:%s solid %s;border-radius:16px;padding:16px;display:flex;justify-content:center">'
      '<div class="vd-retrato" style="width:100%%;max-width:220px">%s</div></div>'
      '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-family:\'Fraunces\',Georgia,serif;font-size:18px;font-weight:600">%s</span>'
      '<span style="font-size:14px;color:#B7BCCB;line-height:1.5">%s</span></div></div>')%(cls,bw,bor,svg,tit,desc)
corpo=('<div class="vd-demo" style="width:1280px;box-sizing:border-box;padding:40px;background:#0D1626;color:#F3EEE2;font-family:\'Source Sans 3\',system-ui,sans-serif;display:flex;flex-direction:column;gap:28px">'
 '<header style="display:flex;flex-direction:column;gap:4px"><span style="font-size:13px;font-weight:600;letter-spacing:0.08em;color:#E3C384">ANIMAÇÕES · PROTÓTIPO 3</span>'
 '<span style="font-family:\'Fraunces\',Georgia,serif;font-size:30px;font-weight:600">O Vidente em ação</span>'
 '<span style="font-size:15px;color:#B7BCCB;max-width:900px">Mesmo modelo dos outros. O gesto dele é a magia do cajado: o orbe pulsa e solta fumaça e faíscas. Quando acha uma ameaça, o círculo mágico atrás dele gira.</span></header>'
 '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px">'+html+'</div></div>')
fonts='<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&amp;family=Source+Code+Pro:wght@400;500&amp;family=Source+Sans+3:wght@400;500;600&amp;display=swap" rel="stylesheet">'
open(S+'/cav/vid-anim.html','w').write('<!doctype html><html><head><meta charset="utf-8">'+fonts+'<style>body{margin:0;background:#0D1626}'+CSS+'</style></head><body>'+shared+corpo+'</body></html>')
dc=('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<title>Vidente em ação · animação</title>\n<script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n'+fonts+'\n<style>body{margin:0}'+CSS+'</style>\n</helmet>\n'
 +shared+'\n'+corpo+'\n</x-dc>\n<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":1280,"height":760}}\'>\nclass Component extends DCLogic {\n  renderVals() { return {}; }\n}\n</script>\n</body>\n</html>\n')
open(S+'/canvas/project/Anim-vidente.dc.html','w').write(dc)
print('ok','{{' in dc)
