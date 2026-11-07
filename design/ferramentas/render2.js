// renderizador simples (com sc-for/sc-if aninhados) para conferir telas localmente
const fs=require('fs');
const [,,arq,propsJson,saida]=process.argv;
const src=fs.readFileSync('canvas/project/'+arq,'utf8');
let body=src.slice(src.indexOf('<x-dc>')+6,src.indexOf('</x-dc>')).replace(/<helmet>[\s\S]*?<\/helmet>/,'');
const code=src.match(/data-dc-script[^>]*>([\s\S]*?)<\/script>/)[1];
class DCLogic{constructor(p){this.props=p}}
const C=new Function('DCLogic',code+';return Component')(DCLogic);
const V=new C(JSON.parse(propsJson)).renderVals();
const svg={cavaleiro:'cav-espada3',arqueira:'arq-gravura5',vidente:'vid',carcereiro:'car'};
const get=(sc,p)=>p.trim().split('.').reduce((o,k)=>o==null?o:o[k],sc);
const embSrc=(()=>{const e=fs.readFileSync('canvas/project/Emblema.dc.html','utf8');return e.slice(e.indexOf('<svg'),e.indexOf('</svg>')+6);})();
const embTons={ouro:{luz:'url(#embLuzO)',ouro:'#F3E3B8',faixa:'#F3EEE2',sombra:'#0D1626',recorte:'#E9CF92',luz2:'#C9A45E',fita:'#B08640'},
 claro:{luz:'url(#embLuzC)',ouro:'#8A6420',faixa:'#8A6420',sombra:'#14203A',recorte:'#F6EEDB',luz2:'#F6EEDB',fita:'#FFF6DE'},
 escuro:{luz:'url(#embLuzE)',ouro:'#D4AF6A',faixa:'#D4AF6A',sombra:'#070D1A',recorte:'#2C4170',luz2:'#3D5283',fita:'#0D1626'}};
const emb=(tom)=>{const c=embTons[tom]||embTons.ouro;return embSrc.replace(/\{\{c\.(\w+)\}\}/g,(_,k)=>c[k]);};
function bloco(t,tag,i){ // acha o fechamento equilibrado da tag que abre em i
  let d=0,re=new RegExp('<(/?)'+tag+'[\\s>]','g');re.lastIndex=i;let m;
  while((m=re.exec(t))){ if(m[1]) {d--; if(!d) return [t.indexOf('>',i)+1,m.index,m.index+tag.length+3];} else d++; }
  throw 'sem fechamento '+tag;
}
function render(t,sc){
  let out='',i=0;
  const re=/<(sc-for|sc-if)\s([^>]*)>/g;let m;
  while((m=re.exec(t))){
    out+=t.slice(i,m.index);
    const [ini,fim,depois]=bloco(t,m[1],m.index), inner=t.slice(ini,fim);
    if(m[1]==='sc-for'){const l=m[2].match(/list="\{\{([^}]+)\}\}"/)[1],v=m[2].match(/as="(\w+)"/)[1];
      out+=(get(sc,l)||[]).map(it=>render(inner,{...sc,[v]:it})).join('');}
    else { const p=m[2].match(/value="\{\{([^}]+)\}\}"/)[1]; if(get(sc,p)) out+=render(inner,sc); }
    i=depois; re.lastIndex=depois;
  }
  t=out+t.slice(i);
  t=t.replace(/<dc-import name="Retrato" quem="([^"]*)"[^>]*><\/dc-import>/g,(_,q)=>fs.readFileSync('cav/'+svg[q.replace(/\{\{([^}]+)\}\}/,(_,p)=>get(sc,p))]+'.svg','utf8'));
  t=t.replace(/<dc-import name="Emblema"(?: tom="([^"]*)")?[^>]*><\/dc-import>/g,(_,tom)=>emb((tom||'ouro').replace(/\{\{([^}]+)\}\}/,(_,p)=>get(sc,p))));
  return t.replace(/\{\{([^}]+)\}\}/g,(_,p)=>get(sc,p));
}
const out=render(body,V);
if(/\{\{|<sc-/.test(out)) console.error('sobrou template');
fs.writeFileSync('cav/'+saida,'<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600&family=Source+Code+Pro&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet"><style>body{margin:0;background:#0D1626}</style></head><body>'+fs.readFileSync('cav/shared.svg','utf8')+out+'</body></html>');
