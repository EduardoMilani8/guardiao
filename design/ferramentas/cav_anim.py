import re, sys
S='/tmp/claude-1000/-home-eduardo-milani-guardiao/0e7ec523-66c8-4587-84d1-f209c20530b0/scratchpad'
svg=open(S+'/cav/cav-espada3.svg').read()

PLUMA_D='M122 60C120 40 136 24 160 20C182 17 200 28 208 44C194 38 180 38 168 42C184 46 196 56 200 70C186 62 170 60 158 64C168 70 174 80 176 90C164 80 148 74 136 72Z'
pl_part='<path style="fill: var(--off, #f7f1e3)" d="%s"></path>\n'%PLUMA_D
assert pl_part in svg; svg=svg.replace(pl_part,'')
h1='<path d="M136 72C148 74 164 80 176 90C170 82 164 74 158 66C148 66 140 68 136 72Z"></path>\n'
h2='<path d="M186 62C192 64 196 66 200 70C194 60 188 52 180 48Z"></path>\n'
for h in (h1,h2): assert h in svg; svg=svg.replace(h,'')
lin='<path d="M128 58C132 30 156 22 180 24M134 62C144 44 164 34 190 36M142 66C154 54 174 48 196 52M150 68C164 62 180 62 194 66M144 72C156 72 166 78 172 86" stroke-width="0.5"></path>\n'
assert lin in svg; svg=svg.replace(lin,'')

ELMO='M90 150V98C90 75 103 58 120 58C137 58 150 75 150 98V150C143 156 132 158 120 158C108 158 97 156 90 150Z'
SELO='M110 192H130V202C130 208 126 212 120 214C114 212 110 208 110 202Z'
defs_add=('<clipPath id="cvElmo"><path d="%s"></path></clipPath>'
 '<linearGradient id="cvLuz" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"></stop>'
 '<stop offset="0.5" stop-color="#fff" stop-opacity="0.85"></stop><stop offset="1" stop-color="#fff" stop-opacity="0"></stop></linearGradient>\n')%ELMO
svg=svg.replace('</defs>',defs_add+'</defs>',1)

pluma=('<g class="cv-pluma">'
 '<path style="fill: var(--off, #f7f1e3)" stroke="#1d1b2b" stroke-width="3.4" stroke-linejoin="round" d="%s"></path>'
 '<path style="fill: var(--off, #f7f1e3)" stroke="#1d1b2b" stroke-width="0.9" stroke-linejoin="round" d="%s"></path>'
 '<g fill="url(#fvH)">%s%s</g>'
 '<g fill="none" stroke="#1d1b2b" stroke-linecap="round">%s</g></g>\n')%(PLUMA_D,PLUMA_D,h1,h2,lin)
u='<use href="#fvParts" stroke="#1d1b2b" stroke-width="3.4"></use>'
assert u in svg
svg=svg.replace(u,'<g class="cv-corpo">\n'+pluma+u,1)
fim='</g>\n<use href="#gFrame"></use>'
assert svg.count(fim)==1
extra=('<g clip-path="url(#cvElmo)"><rect class="cv-brilho" x="40" y="50" width="34" height="120" fill="url(#cvLuz)" transform="skewX(-18)"></rect></g>'
 '<path class="cv-selo" d="%s" fill="#fff6d0"></path>\n</g>\n')%SELO
svg=svg.replace(fim,extra+fim)
svg=svg.replace('aria-label="O Cavaleiro"','aria-label="O Cavaleiro"',1)
open(S+'/anim/cav-anim.svg','w').write(svg)
print(len(svg))
