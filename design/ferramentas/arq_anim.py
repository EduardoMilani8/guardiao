import math
S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/cav/arq-gravura5.svg').read()
def rep(a,b):
    global svg
    assert svg.count(a)==1,a[:60]; svg=svg.replace(a,b)

# corpo inteiro respira como um bloco
rep('<use href="#avParts" stroke="#1d1b2b" stroke-width="3.4"></use>','<g class="ar-corpo">\n<use href="#avParts" stroke="#1d1b2b" stroke-width="3.4"></use>')
# sobrancelhas, olhos e pálpebras separados
rep('<path d="M104 139 Q110 134.5 116 138 M124 138 Q130 134.5 136 139" stroke="#5a2e14"','<path class="ar-sobr" d="M104 139 Q110 134.5 116 138 M124 138 Q130 134.5 136 139" stroke="#5a2e14"')
a='<path d="M105 146 Q110 141.5 115.5 146'
i=svg.index(a); j=svg.index('<path d="M104.5 146.2 Q110 141 116 145.6')
svg=svg[:i]+'<g class="ar-olhos">'+svg[i:j]+'</g>'+svg[j:]
rep('<path d="M104.5 146.2 Q110 141 116 145.6 M124 145.6 Q130 141 135.5 146.2" stroke="#1d1b2b"','<path class="ar-palp" d="M104.5 146.2 Q110 141 116 145.6 M124 145.6 Q130 141 135.5 146.2" stroke="#1d1b2b"')

# folhas no vento (na frente dela)
FOLHA='<path d="M-7 0 C-4 -4.5 4 -4.5 7 0 C4 4.5 -4 4.5 -7 0 Z" stroke="#1d1b2b" stroke-width="0.7" fill="%s"></path><path d="M-6 0 H6" stroke="#1d1b2b" stroke-width="0.4"></path>'
folhas=''
for k,(y,cor,esc,atraso) in enumerate([(112,'#6f9a5a',1.7,0.00),(146,'#d2a654',1.4,0.20),(172,'#5d8a4e',1.8,0.08),(96,'#a8c27a',1.3,0.32),(198,'#6f9a5a',1.5,0.26),(130,'#5d8a4e',1.2,0.40)]):
    folhas+='<g transform="translate(0 %d) scale(%s)"><g class="ar-folha" style="animation-delay:%ss">%s</g></g>'%(y,esc,atraso,FOLHA%cor)
# flechas: saraivada saindo de trás dela para a frente
FLECHA=('<path d="M-16 0 H9" stroke="#1d1b2b" stroke-width="2.6" stroke-linecap="round"></path>'
 '<path d="M-16 0 H9" stroke="#a8743e" stroke-width="1.2" stroke-linecap="round"></path>'
 '<path d="M8 -3.2 L16 0 L8 3.2 Z" fill="#e4e8ee" stroke="#1d1b2b" stroke-width="0.7"></path>'
 '<path d="M-12 0 L-18 -4 L-14 0 L-18 4 Z" fill="#b5483a" stroke="#1d1b2b" stroke-width="0.6"></path>')
flechas=''
pts=[(80,116,0.00),(160,116,0.05),(96,86,0.12),(144,86,0.03),(120,70,0.16),(72,150,0.09),(168,150,0.14),(106,62,0.24),(134,62,0.20),(86,98,0.30),(154,98,0.27),(64,132,0.34),(176,132,0.32)]
for x,y,d in pts:
    ang=math.degrees(math.atan2(y-140,x-120))
    flechas+='<g transform="translate(%d %d) rotate(%.1f)"><g class="ar-flecha" style="animation-delay:%ss">%s</g></g>'%(x,y,ang,d,FLECHA)
fim='</g>\n</g>\n<use href="#gFrame"></use>'
assert svg.count(fim)==1
selo='<path class="ar-selo" d="M120 213 L126 220 L120 227 L114 220 Z" fill="#fff6d0"></path>'
ONDA='<path class="ar-onda" pathLength="300" d="M0 0 C30 -7 70 7 110 0 C140 -6 170 -9 196 -2 C206 2 204 11 196 11 C189 11 187 5 193 3" fill="none" stroke="#fffbe2" stroke-width="%s" stroke-linecap="round" style="animation-delay:%ss"></path>'
ondas=''.join('<g transform="translate(%d %d)">%s</g>'%(x,y,ONDA%(w,d)) for x,y,w,d in [(14,100,2.0,0.0),(20,138,1.6,0.12),(8,168,2.2,0.06),(24,204,1.8,0.2)])
svg=svg.replace(fim,'</g>\n'+selo+'</g>\n<g class="ar-vento">'+ondas+folhas+'</g>\n<g class="ar-saraivada">'+flechas+'</g>\n</g>\n<use href="#gFrame"></use>')
open(S+'/anim/arq-anim.svg','w').write(svg)
print('ok')
