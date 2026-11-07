import math
D='#16121a'
# arco de pedra atrás dele
cx,cy,r1,r2=120,124,54,66
vou=[]
n=11
for i in range(n):
    a0=math.pi+math.pi*i/n; a1=math.pi+math.pi*(i+1)/n
    p=[(cx+r1*math.cos(a0),cy+r1*math.sin(a0)),(cx+r2*math.cos(a0),cy+r2*math.sin(a0)),(cx+r2*math.cos(a1),cy+r2*math.sin(a1)),(cx+r1*math.cos(a1),cy+r1*math.sin(a1))]
    col='#6a5e58' if i%2 else '#74665e'
    if i==n//2: col='#7e6e64'
    vou.append(f'<path d="M{p[0][0]:.1f} {p[0][1]:.1f} L{p[1][0]:.1f} {p[1][1]:.1f} A{r2} {r2} 0 0 1 {p[2][0]:.1f} {p[2][1]:.1f} L{p[3][0]:.1f} {p[3][1]:.1f} A{r1} {r1} 0 0 0 {p[0][0]:.1f} {p[0][1]:.1f} Z" fill="{col}"></path>')
jamb=[]
for k,y in enumerate(range(124,300,20)):
    for x0,x1 in ((cx-r2,cx-r1),(cx+r1,cx+r2)):
        w=0 if k%2 else 3
        jamb.append(f'<path d="M{x0-(w if x0<cx else 0)} {y} H{x1+(w if x0>cx else 0)} V{y+20} H{x0-(w if x0<cx else 0)} Z" fill="{"#6e6159" if k%2 else "#766860"}"></path>')
arch='\n'.join(vou+jamb)
# correntes
def chain(x,y0,y1):
    out=[];y=y0;v=True
    while y<y1:
        if v: out.append(f'<ellipse cx="{x}" cy="{y+3.5}" rx="2" ry="3.6"></ellipse>')
        else: out.append(f'<ellipse cx="{x}" cy="{y+3.5}" rx="1" ry="3.6"></ellipse>')
        y+=5.6; v=not v
    return out
ch=chain(200,38,112)+chain(214,52,138)
chains='\n'.join(ch)
# pedras da parede (irregulares)
import random
random.seed(7)
st=[]
y=0;row=0
while y<300:
    h=random.choice([16,18,20])
    x=-random.randint(0,20)
    while x<240:
        w=random.randint(26,40)
        st.append(f'<rect x="{x+0.8}" y="{y+0.8}" width="{w-1.6}" height="{h-1.6}" rx="3"></rect>')
        x+=w
    y+=h;row+=1
stones='\n'.join(st)
open('car-bits.txt','w').write(arch+'\n@@\n'+chains+'\n@@\n'+stones)
print(len(st))
