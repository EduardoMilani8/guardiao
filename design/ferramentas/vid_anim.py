S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/cav/vid.svg').read()
def rep(a,b):
    global svg
    assert svg.count(a)==1,a[:60]; svg=svg.replace(a,b)
# círculo mágico (anéis, hexagrama e runas) num grupo que gira em volta de 120,150
i=svg.index('<g fill="none" stroke="#e7c983" opacity="0.55">')
j=svg.index('<path d="M190 50 C170 52')
svg=svg[:i]+'<g class="vd-circulo">'+svg[i:j]+'</g>\n'+svg[j:]
# halos do orbe pulsam
rep('<circle cx="55.5" cy="97" r="21" fill="#bfeaf5" opacity="0.2"></circle>','<circle class="vd-halo" cx="55.5" cy="97" r="21" fill="#bfeaf5" opacity="0.2"></circle>')
rep('<circle cx="55.5" cy="97" r="15" fill="#bfeaf5" opacity="0.2"></circle>','<circle class="vd-halo2" cx="55.5" cy="97" r="15" fill="#bfeaf5" opacity="0.2"></circle>')
# corpo inteiro respira como um bloco
rep('<use href="#dvParts" stroke="#14112a" stroke-width="3.4"></use>','<g class="vd-corpo">\n<use href="#dvParts" stroke="#14112a" stroke-width="3.4"></use>')
# brilho dos olhos
rep('<circle cx="110" cy="141" r="5.6" fill="#bfeaf5" opacity="0.35"></circle>','<circle class="vd-olho" cx="110" cy="141" r="5.6" fill="#bfeaf5" opacity="0.35"></circle>')
rep('<circle cx="130" cy="141" r="5.6" fill="#bfeaf5" opacity="0.35"></circle>','<circle class="vd-olho" cx="130" cy="141" r="5.6" fill="#bfeaf5" opacity="0.35"></circle>')
# orbe acende, fumaça mágica e faíscas sobem do orbe
orbe='<circle class="vd-orbe" cx="55.5" cy="97" r="10.5" fill="#f2fdff"></circle>'
fumo=''
for k,(dx,d,w) in enumerate([(0,0.0,2.4),(-5,0.7,1.8),(5,1.4,2.0)]):
    fumo+=('<g transform="translate(%d 0)"><path class="vd-fumo" style="animation-delay:%ss" d="M55.5 88 C49 80 62 72 55 63 C49 55 61 48 55 39 C51 33 57 28 55 22" fill="none" stroke="#d8f6ff" stroke-width="%s" stroke-linecap="round"></path></g>')%(dx,d,w)
faiscas=''
for x,y,d in [(50,84,0.2),(61,82,1.0),(55,80,1.7),(46,90,2.4),(65,90,2.9)]:
    faiscas+='<g transform="translate(%d %d)"><use class="vd-faisca" href="#dvStar" style="animation-delay:%ss" fill="#f2fdff" stroke="#14112a" stroke-width="0.3"></use></g>'%(x,y,d)
fim='</g>\n<use href="#gFrame"></use>'
assert svg.count(fim)==1
svg=svg.replace(fim,orbe+'\n</g>\n<g class="vd-magia">'+fumo+faiscas+'</g>\n</g>\n<use href="#gFrame"></use>')
open(S+'/anim/vid-anim.svg','w').write(svg)
print('ok')
