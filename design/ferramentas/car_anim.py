S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/cav/car.svg').read()
def rep(a,b):
    global svg
    assert svg.count(a)==1,a[:60]; svg=svg.replace(a,b)
PORTA='M66 300 V124 A54 54 0 0 1 174 124 V300 Z'
rep('</defs>','<clipPath id="cvPorta"><path d="%s"></path></clipPath>\n</defs>'%PORTA)
# grade (portão levadiço) que desce na porta escura atrás dele
bars=''.join('<path d="M%d 0 H%d V266 L%d 274 L%d 266 Z"></path>'%(x-1.6,x+1.6,x,x-1.6) for x in range(72,172,10))
horiz=''.join('<path d="M66 %d H174 V%d H66 Z"></path>'%(y,y+3) for y in (40,90,140,190,240))
rebites=''.join('<circle cx="%d" cy="%d" r="1"></circle>'%(x,y+1.5) for y in (40,90,140,190,240) for x in range(72,172,10))
grade=('<g clip-path="url(#cvPorta)"><g class="car-grade">'
 '<g fill="#5a5f6a" stroke="#16121a" stroke-width="0.6" stroke-linejoin="round">'+bars+horiz+'</g>'
 '<g fill="#8a8f99" stroke="#16121a" stroke-width="0.3">'+rebites+'</g>'
 '<path d="M66 0 H174 V274 H66 Z" fill="url(#jvH)" opacity="0.35"></path>'
 '</g></g>\n')
a='<path d="M66 300 V124 A54 54 0 0 1 174 124 V300 Z" fill="url(#jvS)" opacity="0.7"></path>\n'
rep(a,a+grade)
# correntes balançam juntas, presas no alto
i=svg.index('<g fill="#5a5f6a" stroke="#16121a" stroke-width="0.5">')
j=svg.index('<circle cx="38" cy="130" r="34"')
svg=svg[:i]+'<g class="car-correntes">'+svg[i:j]+'</g>\n'+svg[j:]
# lanterna: brilho e chama
rep('<circle cx="38" cy="130" r="34" fill="#ffc56a" opacity="0.18"></circle>','<circle class="car-luz" cx="38" cy="130" r="34" fill="#ffc56a" opacity="0.18"></circle>')
rep('<circle cx="38" cy="130" r="20" fill="#ffc56a" opacity="0.22"></circle>','<circle class="car-luz2" cx="38" cy="130" r="20" fill="#ffc56a" opacity="0.22"></circle>')
rep('<path d="M38 122 C35 126 35 131 38 134 C41 131 41 126 38 122 Z" fill="#fff4cc"','<path class="car-chama" d="M38 122 C35 126 35 131 38 134 C41 131 41 126 38 122 Z" fill="#fff4cc"')
# luz da lanterna dançando na parede (por cima do fundo, por baixo da figura)
rep('<use href="#jvParts" stroke="#16121a" stroke-width="3.4"></use>','<circle class="car-parede" cx="38" cy="130" r="70" fill="#ffc56a" opacity="0"></circle>\n<g class="car-corpo">\n<use href="#jvParts" stroke="#16121a" stroke-width="3.4"></use>')
fim='</g>\n</g>\n<use href="#gFrame"></use>'
assert svg.count(fim)==1
svg=svg.replace(fim,'</g>\n</g>\n</g>\n<use href="#gFrame"></use>')
open(S+'/anim/car-anim.svg','w').write(svg)
print('ok')
