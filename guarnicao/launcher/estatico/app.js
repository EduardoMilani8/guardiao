'use strict';
/* Painel da Guarnição. Lê o estado do servidor local, desenha a muralha e conversa
   com ele para varrer, trancar, caçar e atualizar. Nada aqui recebe ou manda
   caminhos de arquivo: o servidor dá ids, e a página só devolve esses ids. */

const $ = (seletor) => document.querySelector(seletor);

// Todo texto que vem de fora (nomes de arquivo, mensagens) passa por aqui.
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (valor) => String(valor ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);

const PERSONAGENS = [
  { quem: 'cavaleiro', nome: 'O Cavaleiro', papel: 'ASSINATURAS', classe: 'cv-retrato',
    faz: 'Reconhece ameaças já conhecidas pela base do ClamAV.', achou: 'Reconhecida pelo Cavaleiro' },
  { quem: 'arqueira', nome: 'A Arqueira', papel: 'REGRAS', classe: 'ar-retrato',
    faz: 'Mira nos padrões que denunciam famílias de malware.', achou: 'Apontada pela Arqueira' },
  { quem: 'vidente', nome: 'O Vidente', papel: 'SINAIS SUSPEITOS', classe: 'vd-retrato',
    faz: 'Percebe comportamento de invasor, mesmo sem assinatura.', achou: 'Percebido pelo Vidente' },
  { quem: 'carcereiro', nome: 'O Carcereiro', papel: 'QUARENTENA', classe: 'car-retrato',
    faz: 'Tranca o que você mandar. Dá para devolver depois.' },
];
// Qual camada do motor é de qual personagem.
const DONO = { hash: 'cavaleiro', clamav: 'cavaleiro', yara: 'arqueira', heuristica: 'vidente',
  virustotal: 'vidente', compactado: 'arqueira' };
const quemAchou = (camada) => PERSONAGENS.find((p) => p.quem === (DONO[camada] || 'vidente')).achou;

// Brilho de cada personagem: n normal, a agindo, p achou ameaça, w aviso, t trancou, z fora da vez.
const BRILHO = {
  n: 'none', z: 'none',
  a: 'drop-shadow(0 0 16px rgba(212,175,106,.85))',
  p: 'drop-shadow(0 0 18px rgba(255,90,70,.9))',
  w: 'drop-shadow(0 0 16px rgba(240,182,90,.85))',
  t: 'drop-shadow(0 0 18px rgba(143,211,176,.9))',
};
const ANIMACAO = { z: 'm-inativo', a: 'm-agindo', p: 'm-achou', t: 'm-trancou' };

// O céu muda com o que está acontecendo.
const CEU = {
  repouso: { horizonte: 'rgba(90,120,180,.28)', lua: '#fffbe8', vento: 3.2 },
  varrendo: { horizonte: 'rgba(212,175,106,.24)', lua: '#fffbe8', vento: 1.6 },
  ameaca: { horizonte: 'rgba(255,80,50,.55)', lua: '#ffd9c8', vento: 1.1 },
  atencao: { horizonte: 'rgba(240,182,90,.32)', lua: '#fff3d6', vento: 2.4 },
  cacada: { horizonte: 'rgba(150,110,255,.38)', lua: '#ece4ff', vento: 1.8 },
};
CEU.parcial = CEU.repouso; CEU.protetor = CEU.atencao; CEU.cacando = CEU.cacada;

const TOCHA_ACESA = '<div class="mu-tocha-luz"></div><svg class="mu-tocha" viewBox="0 0 22 64"><path class="mu-ch" d="M11 0 C16 7 19 12 17 18 C15 22 7 22 5 18 C3 12 6 7 11 0 Z" fill="#ffb347"></path><path class="mu-ch" d="M11 8 C13 11 14 14 13 17 C12 19 10 19 9 17 C8 14 9 11 11 8 Z" fill="#fff0b0"></path><path d="M6 20 H16 L14 40 H8 Z" fill="#5a381a" stroke="#0b0c10"></path><path d="M3 42 H19 V46 H3 Z M9 46 H13 V62 H9 Z" fill="#3a3540" stroke="#0b0c10"></path></svg>';
const TOCHA_APAGADA = '<svg class="mu-tocha" viewBox="0 0 22 64"><path d="M6 20 H16 L14 40 H8 Z" fill="#3a2614" stroke="#0b0c10"></path><path d="M7 20 C8 16 14 16 15 20 Z" fill="#1a1410"></path><path d="M3 42 H19 V46 H3 Z M9 46 H13 V62 H9 Z" fill="#2c2a32" stroke="#0b0c10"></path></svg>';
const FOGO = '<div class="mu-fogo-luz"></div><svg class="mu-chama mu-chama-grande" viewBox="0 0 48 70"><path d="M24 0 C36 18 46 30 42 48 C39 62 9 62 6 48 C2 30 12 18 24 0 Z" fill="#ff7a2a"></path><path d="M24 22 C31 32 34 40 31 50 C28 56 20 56 17 50 C14 40 17 32 24 22 Z" fill="#ffd36a"></path></svg><svg class="mu-chama mu-chama-2" viewBox="0 0 28 40" style="left: 30px"><path d="M14 0 C21 10 26 18 24 28 C22 36 6 36 4 28 C2 18 7 10 14 0 Z" fill="#ff5a24"></path></svg>';
const BRASA = '<svg class="mu-chama" viewBox="0 0 28 40"><path d="M14 8 C20 16 24 22 22 30 C20 36 8 36 6 30 C4 22 8 16 14 8 Z" fill="#ffa040"></path><path d="M14 20 C17 24 18 28 17 31 C15 34 13 34 11 31 C10 28 11 24 14 20 Z" fill="#ffe08a"></path></svg>';
const FUMACA = '<div><div class="mu-fumo"></div><div class="mu-fumo"></div><div class="mu-fumo"></div></div>';
const SELO_TRANCADO = '<div class="cr-selo" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 16 16"><path d="M4.5 7 V5 a3.5 3.5 0 0 1 7 0 V7" fill="none" stroke="currentColor" stroke-width="1.8"></path><rect x="2.5" y="7" width="11" height="8" rx="1.6" fill="currentColor"></rect></svg>TRANCADO</div>';

// ---- o que a página sabe agora ----
const est = {
  servidor: null,       // /api/estado
  historico: null,      // /api/historico
  varredura: null,      // varredura rodando nesta página
  cacando: false,
  ocupado: false,       // um pedido em andamento (atualizar, trancar todas...)
  trancouAte: 0,        // até quando o Carcereiro mostra a grade descendo
  cacadaFechada: null,  // a pessoa fechou o quadro desta caçada
};
let fonte = null;       // EventSource da varredura
let modosAntes = [];

// ---- formatos ----
const numero = (n) => Number(n || 0).toLocaleString('pt-BR');
const plural = (n, um, varios) => `${numero(n)} ${n === 1 ? um : varios}`;
const paraData = (v) => (v instanceof Date ? v : new Date(typeof v === 'number' ? v * 1000 : v));
const meiaNoite = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

function quando(valor) {
  const d = paraData(valor);
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const dias = Math.round((meiaNoite(new Date()) - meiaNoite(d)) / 864e5);
  if (dias === 0) return `hoje, ${hora}`;
  if (dias === 1) return `ontem, ${hora}`;
  if (dias === -1) return `amanhã, ${hora}`;
  if (Math.abs(dias) < 7) return `${d.toLocaleDateString('pt-BR', { weekday: 'long' }).replace('-feira', '')}, ${hora}`;
  return `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })}, ${hora}`;
}

function ha(segundos) {
  if (segundos == null) return 'nunca';
  const s = Math.max(0, Date.now() / 1000 - segundos);
  if (s < 90) return 'agora há pouco';
  if (s < 3600) return `há ${Math.round(s / 60)} min`;
  if (s < 86400 * 2) return `há ${Math.round(s / 3600)} h`;
  return `há ${Math.round(s / 86400)} dias`;
}

const nomeDoTipo = (tipo) => (tipo === 'rápida' ? 'Rápida' : tipo === 'completa' ? 'Completa'
  : `Pasta · ${tipo.split('/').filter(Boolean).pop() || tipo}`);

function resultado(r) {
  if (!r.ameacas && !r.suspeitos) return { texto: '✓ Tudo limpo', cor: 'ok' };
  const partes = [];
  if (r.ameacas) partes.push(plural(r.ameacas, 'ameaça', 'ameaças'));
  if (r.suspeitos) partes.push(plural(r.suspeitos, 'suspeito', 'suspeitos'));
  const trancados = r.achados.length > 0 && r.achados.every((a) => a.trancado);
  // "ameaça" pede o feminino; com suspeito no meio, fica o masculino.
  const fem = !r.suspeitos;
  if (trancados) return { texto: `${partes.join(' · ')} · ${fem ? 'trancada' : 'trancado'}${r.achados.length > 1 ? 's' : ''}`, cor: '' };
  return { texto: partes.join(' · '), cor: r.ameacas ? 'perigo' : 'aviso' };
}

// ---- conversa com o servidor ----
async function pedir(rota, dados) {
  const resposta = await fetch(rota, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados || {}),
  });
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(corpo.erro || `o servidor respondeu ${resposta.status}`);
  return corpo;
}

async function carregar() {
  try {
    const [servidor, historico] = await Promise.all([
      fetch('/api/estado').then((r) => r.json()), fetch('/api/historico').then((r) => r.json())]);
    est.servidor = servidor;
    est.historico = historico;
  } catch {
    recado('Não consegui falar com a Guarnição. O launcher ainda está aberto?', true);
  }
  desenhar();
  if (!$('#pergaminho').hidden) desenharHistorico();
}

let recadoTempo;
function recado(texto, erro = false) {
  const el = $('#recado');
  el.textContent = texto;
  el.classList.toggle('erro', erro);
  el.hidden = false;
  clearTimeout(recadoTempo);
  recadoTempo = setTimeout(() => { el.hidden = true; }, erro ? 8000 : 5000);
}

// ---- o que mostrar ----
function cacadaAberta() {
  const c = est.servidor?.cacada;
  return c && c.achados.length && est.cacadaFechada !== c.quando ? c : null;
}

function visao() {
  if (est.varredura) return 'varrendo';
  if (est.cacando) return 'cacando';
  if (!est.servidor || !est.historico) return 'repouso';
  if (est.historico.pendentes.length) return 'ameaca';
  if (cacadaAberta()) return 'cacada';
  const { protetor, monitor, bases } = est.servidor;
  if ((protetor.instalado && !protetor.ativo) || (monitor.instalado && !monitor.ativo)) return 'protetor';
  if (bases.avisos.length || bases.freshclam_parado) return 'atencao';
  // Só a completa: a rápida sempre tem itens do sistema fora do alcance, e repetir
  // isso todo dia ensinaria a ignorar o painel.
  const ultima = est.historico.registros[0];
  if (ultima && ultima.tipo === 'completa' && ultima.sem_permissao && !ultima.ameacas && !ultima.suspeitos) return 'parcial';
  return 'repouso';
}

function modos(v) {
  const m = { cavaleiro: 'n', arqueira: 'n', vidente: 'n', carcereiro: 'n' };
  if (v === 'varrendo') {
    Object.assign(m, { cavaleiro: 'a', arqueira: 'a', vidente: 'a', carcereiro: 'z' });
    for (const a of est.varredura.achados) {
      const dono = DONO[a.camada] || 'vidente';
      m[dono] = a.veredito === 'ameaca' ? 'p' : (m[dono] === 'p' ? 'p' : 'w');
    }
  } else if (v === 'cacando') {
    Object.assign(m, { cavaleiro: 'z', arqueira: 'z', vidente: 'a', carcereiro: 'z' });
  } else if (v === 'cacada') {
    Object.assign(m, { cavaleiro: 'z', arqueira: 'z', vidente: 'p', carcereiro: 'z' });
  } else if (v === 'ameaca') {
    Object.assign(m, { cavaleiro: 'z', arqueira: 'z', vidente: 'z', carcereiro: 'a' });
    for (const a of est.historico.pendentes) {
      const dono = DONO[a.camada] || 'vidente';
      m[dono] = a.veredito === 'ameaca' ? 'p' : (m[dono] === 'p' ? 'p' : 'w');
    }
  } else if (v === 'atencao') {
    m.cavaleiro = 'w';
  }
  if (Date.now() < est.trancouAte) m.carcereiro = 't';
  return PERSONAGENS.map((p) => m[p.quem]);
}

function titulo(v) {
  const s = est.servidor;
  switch (v) {
    case 'varrendo': return { texto: 'Procurando ameaças…', cor: '' };
    case 'cacando': return { texto: 'O Vidente está caçando…', cor: '' };
    case 'ameaca': {
      const p = est.historico.pendentes;
      const ameacas = p.filter((a) => a.veredito === 'ameaca').length;
      return ameacas
        ? { texto: p.length === 1 ? '1 arquivo perigoso' : `${numero(p.length)} arquivos perigosos`, cor: 'perigo' }
        : { texto: p.length === 1 ? '1 arquivo suspeito' : `${numero(p.length)} arquivos suspeitos`, cor: 'aviso' };
    }
    case 'cacada': {
      const n = cacadaAberta().achados.length;
      return { texto: `O Vidente achou ${n === 1 ? '1 sinal' : `${numero(n)} sinais`} de invasão`, cor: 'perigo' };
    }
    case 'protetor':
      return { texto: s.protetor.instalado && !s.protetor.ativo ? 'O Protetor está desligado' : 'O Monitor está desligado', cor: 'aviso' };
    case 'atencao': return { texto: 'Suas bases estão desatualizadas', cor: 'aviso' };
    case 'parcial': return { texto: 'Tudo limpo no que deu para ler', cor: '' };
    default: return { texto: 'Você está protegido', cor: '' };
  }
}

function resumo(v) {
  const s = est.servidor; const h = est.historico;
  const r = (rot, val, cor = '') => ({ rot, val, cor });
  const ultima = h?.registros[0];
  const ultimaTexto = ultima ? `${nomeDoTipo(ultima.tipo)} · ${quando(ultima.inicio)}` : 'Nenhuma ainda';
  const bases = s ? (s.bases.conferidas ? `Atualizadas ${ha(s.bases.conferidas)}` : 'Nunca atualizadas') : '…';
  if (v === 'varrendo') {
    const vr = est.varredura;
    const pct = vr.total ? Math.min(100, Math.round((vr.vistos / vr.total) * 100)) : 0;
    const ameacas = vr.achados.filter((a) => a.veredito === 'ameaca').length;
    const suspeitos = vr.achados.length - ameacas;
    const achou = [ameacas && plural(ameacas, 'ameaça', 'ameaças'), suspeitos && plural(suspeitos, 'suspeito', 'suspeitos')].filter(Boolean);
    return [r('Varredura', vr.rotulo), r('Arquivos', vr.total ? `${numero(vr.vistos)} de ${numero(vr.total)}` : `${numero(vr.vistos)}…`),
      r('Andamento', vr.total ? `${pct}%` : 'preparando…', 'ouro'),
      achou.length ? r('Encontrados', achou.join(' · '), ameacas ? 'perigo' : 'aviso') : r('Encontrados', 'Nada até agora', 'ok')];
  }
  if (v === 'cacando') {
    return [r('Caçada', 'Em andamento', 'ouro'), r('Onde olha', 'Processos, serviços e inicialização'),
      r('O que muda', 'Nada: só mostra'), r('Última varredura', ultimaTexto)];
  }
  if (v === 'ameaca') {
    const p = h.pendentes; const ameacas = p.filter((a) => a.veredito === 'ameaca').length;
    return [r('Ameaças', numero(ameacas), ameacas ? 'perigo' : ''), r('Suspeitos', numero(p.length - ameacas), p.length - ameacas ? 'aviso' : ''),
      r('Varredura', ultimaTexto), r('Arquivos verificados', ultima ? numero(ultima.total) : '—')];
  }
  if (v === 'cacada') {
    const c = cacadaAberta(); const graves = c.achados.filter((a) => a.gravidade === 'alta').length;
    return [r('Caçada', quando(c.quando)), r('Sinais graves', numero(graves), graves ? 'perigo' : ''),
      r('Sinais médios', numero(c.achados.length - graves), c.achados.length - graves ? 'aviso' : ''), r('O que mudou', 'Nada: só mostra')];
  }
  if (v === 'protetor') {
    const qual = s.protetor.instalado && !s.protetor.ativo ? s.protetor : s.monitor;
    return [r(qual === s.protetor ? 'Protetor' : 'Monitor', 'Desligado', 'aviso'), r('Desde', qual.desde ? quando(qual.desde) : '—', 'aviso'),
      r('Outras camadas', '✓ De guarda', 'ok'), r('Última varredura', ultima ? quando(ultima.inicio) : 'Nenhuma ainda')];
  }
  if (v === 'atencao') {
    return [r('Última atualização', s.bases.conferidas ? ha(s.bases.conferidas) : 'Nunca', 'aviso'),
      r('Serviço das bases', s.bases.freshclam_parado ? 'Parado' : 'Ligado', s.bases.freshclam_parado ? 'aviso' : ''),
      r('Outras camadas', '✓ De guarda', 'ok'), r('Última varredura', ultima ? quando(ultima.inicio) : 'Nenhuma ainda')];
  }
  const res = ultima ? resultado(ultima) : { texto: '—', cor: '' };
  const linhas = [r('Última varredura', ultimaTexto), r('Arquivos verificados', ultima ? numero(ultima.total) : '—'),
    r('Resultado', res.texto, res.cor)];
  linhas.push(v === 'parcial' ? r('Ficaram de fora', `${numero(ultima.sem_permissao)} sem permissão`, 'aviso') : r('Bases de ameaças', bases));
  return linhas;
}

// ---- desenho ----
function desenharCeu(v) {
  const ceu = CEU[v];
  $('#horizonte').style.background = `radial-gradient(ellipse 80% 75% at 50% 100%, ${ceu.horizonte}, transparent 72%)`;
  $('#lua').style.backgroundColor = ceu.lua;
  $('#bandeira').style.animationDuration = `${ceu.vento}s`;
  $('#horizonte-fogo').hidden = v !== 'ameaca';
  const brasa = v === 'ameaca' ? 'fogo' : ['atencao', 'protetor'].includes(v) ? 'fumaca' : ['varrendo', 'cacando', 'cacada'].includes(v) ? 'brasa' : '';
  const el = $('#braseiro');
  if (el.dataset.tipo !== brasa) {
    el.dataset.tipo = brasa;
    el.innerHTML = { fogo: FOGO, fumaca: FUMACA, brasa: BRASA }[brasa] || '';
  }
}

function desenharEstrelas() {
  // Posições fixas (sempre as mesmas), algumas piscam: o mesmo céu do desenho aprovado.
  let semente = 7;
  const sorteio = () => { semente = (semente * 9301 + 49297) % 233280; return semente / 233280; };
  let svg = '';
  for (let k = 0; k < 90; k += 1) {
    const x = Math.round(sorteio() * 1280); const y = Math.round(sorteio() * 470);
    const r = (0.5 + sorteio() * 1.3).toFixed(2); const o = (0.35 + sorteio() * 0.6).toFixed(2);
    const d = (sorteio() * 4).toFixed(2);
    svg += `<circle cx="${x}" cy="${y}" r="${r}" fill="#ffffff" opacity="${o}" class="${k % 3 === 0 ? 'mu-pisca' : ''}" style="animation-delay: ${d}s"></circle>`;
  }
  $('#estrelas').innerHTML = svg;
}

async function montarGuardioes() {
  const [comum, ...retratos] = await Promise.all(['comum', ...PERSONAGENS.map((p) => p.quem)].map(
    (nome) => fetch(`/estatico/arte/${nome}.svg`).then((r) => r.text())));
  $('#arte-comum').innerHTML = comum;
  $('#ameias').innerHTML = PERSONAGENS.map((p, i) => `
    <div class="mu-merlao" aria-hidden="true" data-tocha="${i}"></div>
    <article class="mu-sentinela" aria-label="${esc(p.nome)}" id="sentinela-${p.quem}">
      <div class="mu-retrato ${p.classe}">${retratos[i]}${p.quem === 'carcereiro' ? SELO_TRANCADO : ''}</div>
    </article>`).join('') + '<div class="mu-merlao" aria-hidden="true"></div>';
  $('#placas').innerHTML = PERSONAGENS.map((p) => `<div></div><div class="mu-placa-caixa" id="placa-${p.quem}">
    <div class="mu-placa"><strong>${esc(p.nome)}</strong><span>${esc(p.papel)}</span></div>
    <p class="mu-faz">${esc(p.faz)}</p></div>`).join('') + '<div></div>';
}

function reiniciarAnimacao(el, classe) {
  el.classList.remove(classe);
  void el.offsetWidth;   // força o navegador a notar a troca e tocar de novo
  el.classList.add(classe);
}

function desenharGuardioes(v) {
  const lista = modos(v);
  PERSONAGENS.forEach((p, i) => {
    const modo = lista[i]; const antes = modosAntes[i];
    const sentinela = $(`#sentinela-${p.quem}`);
    if (!sentinela) return;
    sentinela.querySelector('.mu-retrato').style.filter = BRILHO[modo];
    $(`#placa-${p.quem}`).style.opacity = modo === 'z' ? '0.5' : '1';
    const merlao = document.querySelector(`[data-tocha="${i}"]`);
    const acesa = ['a', 'p', 'w', 't'].includes(modo);
    if (merlao.dataset.acesa !== String(acesa)) {
      merlao.dataset.acesa = String(acesa);
      merlao.innerHTML = acesa ? TOCHA_ACESA : TOCHA_APAGADA;
    }
    if (modo === antes) return;
    sentinela.classList.remove('m-inativo', 'm-entrada', 'm-agindo', 'm-achou', 'm-trancou');
    if (modo === 'a' && antes !== 'p') {
      // Chegou a vez: entrada curta, depois o ciclo de quem está trabalhando.
      reiniciarAnimacao(sentinela, 'm-entrada');
      setTimeout(() => {
        if (sentinela.classList.contains('m-entrada')) {
          sentinela.classList.replace('m-entrada', 'm-agindo');
        }
      }, 1000);
    } else if (ANIMACAO[modo]) {
      reiniciarAnimacao(sentinela, ANIMACAO[modo]);
    }
  });
  modosAntes = lista;
}

function linhaFundo(nome, desc, st, cor) {
  return `<div class="mu-linha"><div><div style="font-weight: 600">${esc(nome)}</div><small>${esc(desc)}</small></div>
    <span class="mu-st ${cor}">${esc(st)}</span></div>`;
}

function desenharFundo() {
  const s = est.servidor;
  if (!s) { $('#fundo').innerHTML = '<div class="mu-vazio">Carregando…</div>'; return; }
  const servico = (sv, nome, desc) => {
    if (!sv.instalado) return linhaFundo(nome, 'Não instalado', 'Desligado', '');
    return sv.ativo ? linhaFundo(nome, desc, 'Ligado', 'ok')
      : linhaFundo(nome, sv.desde ? `Parado desde ${quando(sv.desde)}` : 'Parado', 'Desligado', 'aviso');
  };
  const proxAtualizar = s.proximas.atualizar
    ? `De hora em hora · próxima às ${paraData(s.proximas.atualizar).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
    : 'De hora em hora';
  const velhas = s.bases.avisos.length || s.bases.freshclam_parado;
  const prox = [s.proximas.rapida, s.proximas.completa].filter(Boolean).sort()[0];
  $('#fundo').innerHTML = [
    servico(s.protetor, 'Protetor', 'Analisa cada programa ao ser executado'),
    servico(s.monitor, 'Monitor', 'Downloads concluídos e processos estranhos'),
    linhaFundo('Atualização das bases', velhas && s.bases.freshclam_parado ? 'Serviço do ClamAV parado' : proxAtualizar,
      ha(s.bases.conferidas), velhas ? 'aviso' : ''),
    linhaFundo('Varreduras agendadas', 'Rápida todo dia · completa aos domingos',
      prox ? quando(prox) : 'Desligadas', prox ? '' : 'aviso'),
  ].join('');
}

function desenharUltimas() {
  const h = est.historico;
  if (!h) return;
  const lista = h.registros.slice(0, 3);
  $('#ultimas').innerHTML = lista.length ? lista.map((r) => {
    const res = resultado(r);
    return `<div class="mu-linha"><div><div style="font-weight: 600">${esc(nomeDoTipo(r.tipo))}</div>
      <small>${esc(quando(r.inicio))} · ${esc(plural(r.total, 'arquivo', 'arquivos'))}</small></div>
      <span class="mu-st ${res.cor}">${esc(res.texto)}</span></div>`;
  }).join('') : '<div class="mu-vazio">Nenhuma varredura ainda. Comece pela rápida: leva poucos segundos.</div>';
}

const BOTOES_INICIO = `<button type="button" class="mu-btn mu-btn-p" data-acao="varrer" data-alvo="rapida">Varredura rápida</button>
  <button type="button" class="mu-btn" data-acao="varrer" data-alvo="completa">Varredura completa</button>
  <button type="button" class="mu-btn" data-acao="pasta">Escolher pasta</button>
  <button type="button" class="mu-btn" data-acao="cacar" title="O Vidente procura persistência e programas escondidos já instalados">Caçar invasores escondidos</button>`;

const copiar = (comando, rotulo = 'Copiar comando', principal = false) =>
  `<button type="button" class="mu-btn${principal ? ' mu-btn-p' : ''}" data-acao="copiar" data-texto="${esc(comando)}">${esc(rotulo)}</button>`;

function desenharAcoes(v) {
  const acoes = $('#acoes'); const alertas = $('#alertas');
  const ocupado = est.ocupado ? ' disabled' : '';
  if (v === 'varrendo') {
    acoes.innerHTML = '<button type="button" class="mu-btn" data-acao="parar">Parar varredura</button>';
  } else if (v === 'cacando') {
    acoes.innerHTML = '';
  } else if (['repouso', 'parcial', 'protetor'].includes(v)) {
    acoes.innerHTML = BOTOES_INICIO;
  } else {
    acoes.innerHTML = '';
  }

  const s = est.servidor; const h = est.historico;
  let html = '';
  const achadosAoVivo = v === 'varrendo' ? est.varredura.achados : [];
  if (v === 'ameaca' || achadosAoVivo.length) {
    const lista = v === 'ameaca' ? h.pendentes : achadosAoVivo;
    html += `<section class="mu-painel mu-alerta perigo" aria-labelledby="achados">
      <div class="mu-cabeca"><h2 id="achados">O que foi encontrado</h2>
      ${lista.length > 1 && v === 'ameaca' ? `<button type="button" class="mu-btn mu-btn-p" data-acao="trancar-todas"${ocupado}>Trancar todas</button>` : ''}</div>
      ${lista.map((a) => {
        const ameaca = a.veredito === 'ameaca';
        const pasta = (a.completo || a.caminho || '').split('/').slice(0, -1).join('/').replace(/^\/home\/[^/]+/, '~');
        const porque = ameaca ? `${a.ameaca ? `${a.ameaca} · ` : ''}${quemAchou(a.camada)}` : `${(a.motivos || [])[0] || 'Sinais suspeitos'} · ${quemAchou(a.camada).toLowerCase()}`;
        return `<div class="mu-linha mu-linha-acao"><span class="mu-etiqueta ${ameaca ? 'perigo' : 'aviso'}">${ameaca ? 'Ameaça' : 'Suspeito'}</span>
          <div><span class="mu-nome-arq">${esc(a.nome)}</span><small>${esc(porque)}${pasta ? ` · ${esc(pasta)}` : ''}</small></div>
          ${v === 'ameaca' ? `<button type="button" class="mu-btn" data-acao="trancar" data-id="${esc(a.id)}"${ocupado}>Trancar</button>` : ''}</div>`;
      }).join('')}
      <p class="mu-nota">${v === 'ameaca' ? 'Trancar isola o arquivo na quarentena. Dá para devolver depois.' : 'Quando a varredura terminar, você escolhe o que trancar.'}</p>
    </section>`;
  }
  if (v === 'atencao') {
    const parado = s.bases.freshclam_parado;
    html += `<section class="mu-painel mu-alerta aviso" aria-labelledby="corrigir"><h2 id="corrigir">Como resolver</h2>
      ${parado ? `<p>O serviço que atualiza as assinaturas do ClamAV está parado. Para religar, no terminal:</p>
        <code class="mu-comando">${esc(s.bases.ligar_freshclam)}</code>`
      : `<p>${s.bases.avisos.map(esc).join('<br>')}</p>`}
      <div class="mu-acoes"><button type="button" class="mu-btn mu-btn-p" data-acao="atualizar"${ocupado}>Atualizar agora</button>
      ${parado ? copiar(s.bases.ligar_freshclam) : ''}</div></section>`;
  }
  if (v === 'cacada') {
    const c = cacadaAberta();
    html += `<section class="mu-painel mu-alerta cacada" aria-labelledby="sinais">
      <div class="mu-cabeca"><h2 id="sinais">O que o Vidente percebeu</h2>
      <div class="mu-acoes"><button type="button" class="mu-btn" data-acao="cacar">Caçar de novo</button>
      <button type="button" class="mu-btn" data-acao="fechar-cacada">Fechar</button></div></div>
      <p>A caçada só mostra: nada foi apagado nem mudado. Cada item diz o que encontrou e onde.</p>
      ${c.achados.map((a) => `<div class="mu-linha mu-linha-acao">
        <span class="mu-etiqueta ${a.gravidade === 'alta' ? 'perigo' : 'aviso'}">${a.gravidade === 'alta' ? 'Grave' : 'Médio'}</span>
        <div><div style="font-weight: 600">${esc(a.categoria)}</div><span class="mu-nome-arq">${esc(a.arquivo)}</span><small>${esc(a.mensagem)}</small></div></div>`).join('')}
      <p class="mu-nota">Sem administrador, só os seus processos foram olhados. Para olhar todos: <code>sudo .venv/bin/python -m guarnicao cacar</code></p>
    </section>`;
  }
  if (v === 'parcial') {
    const ultima = h.registros[0];
    html += `<section class="mu-painel mu-alerta aviso" aria-labelledby="defora">
      <h2 id="defora">${esc(plural(ultima.sem_permissao, 'item ficou', 'itens ficaram'))} de fora</h2>
      <p>São pastas do sistema que a sua conta não tem permissão de ler. O que deu para ler está limpo. Para incluir esses itens, rode a varredura como administrador:</p>
      <code class="mu-comando">sudo .venv/bin/python -m guarnicao varrer --completa</code>
      <div class="mu-acoes">${copiar('sudo .venv/bin/python -m guarnicao varrer --completa')}</div></section>`;
  }
  if (v === 'protetor') {
    const protetorParado = s.protetor.instalado && !s.protetor.ativo;
    const comando = protetorParado ? s.protetor.ligar : s.monitor.ligar;
    html += `<section class="mu-painel mu-alerta aviso" aria-labelledby="religar"><h2 id="religar">Como religar</h2>
      <p>${protetorParado
        ? 'Sem o Protetor, um programa perigoso pode rodar antes de ser analisado. As varreduras e o Monitor continuam funcionando.'
        : 'Sem o Monitor, os downloads novos não são analisados na hora. O Protetor e as varreduras continuam funcionando.'} Para religar, no terminal:</p>
      <code class="mu-comando">${esc(comando)}</code>
      ${protetorParado && s.monitor.instalado && !s.monitor.ativo ? `<p class="mu-nota">O Monitor também parou. Para ele, o comando é outro (sem sudo): <code>${esc(s.monitor.ligar)}</code></p>` : ''}
      <div class="mu-acoes">${copiar(comando, 'Copiar comando', true)}</div></section>`;
  }
  alertas.innerHTML = html;
  alertas.style.display = html ? 'flex' : 'none';
  alertas.style.flexDirection = 'column';
  alertas.style.gap = '20px';
}

function desenhar() {
  const v = visao();
  const t = titulo(v);
  const h1 = $('#titulo');
  h1.textContent = t.texto;
  h1.className = `mu-titulo ${t.cor}`;
  if (!$('#muralha').hidden) document.title = v === 'repouso' ? 'Guarnição' : `${t.texto} · Guarnição`;
  $('#resumo').innerHTML = resumo(v).map((r) => `<div><dt>${esc(r.rot)}</dt><dd class="${r.cor}">${esc(r.val)}</dd></div>`).join('');
  const prog = $('#progresso');
  prog.hidden = v !== 'varrendo';
  if (v === 'varrendo') {
    const vr = est.varredura;
    const pct = vr.total ? Math.min(100, (vr.vistos / vr.total) * 100) : 0;
    $('#barra div').style.width = `${pct}%`;
    $('#barra').setAttribute('aria-valuenow', String(Math.round(pct)));
    // Antes do primeiro arquivo, cada processo ainda está carregando as regras.
    $('#arquivo-atual').textContent = vr.atual || 'preparando os guardiões…';
  }
  desenharCeu(v);
  desenharGuardioes(v);
  desenharAcoes(v);
  desenharFundo();
  desenharUltimas();
}

// ---- ações ----
function varrer(alvo, id, nomePasta) {
  if (fonte) return;
  const rotulo = alvo === 'rapida' ? 'Rápida' : alvo === 'completa' ? 'Completa' : `Pasta · ${nomePasta}`;
  est.varredura = { alvo, rotulo, vistos: 0, total: 0, atual: '', achados: [] };
  desenhar();
  fonte = new EventSource(`/api/varrer?alvo=${encodeURIComponent(alvo)}${id ? `&id=${encodeURIComponent(id)}` : ''}`);
  let ultimoDesenho = 0;
  fonte.onmessage = (evento) => {
    const d = JSON.parse(evento.data);
    const vr = est.varredura;
    if (!vr) return;
    if (d.tipo === 'progresso') {
      vr.vistos = d.vistos; vr.total = d.total; vr.atual = d.atual || vr.atual;
    } else if (d.tipo === 'arquivo') {
      vr.achados.push(d);
    } else if (d.tipo === 'fim') {
      terminar(d);
      return;
    }
    // Progresso chega em rajadas: redesenhar no máximo umas 8 vezes por segundo.
    const agora = performance.now();
    if (d.tipo === 'arquivo' || agora - ultimoDesenho > 120) { ultimoDesenho = agora; desenhar(); }
  };
  fonte.onerror = () => {
    // Sem isto o EventSource reconectaria sozinho e começaria outra varredura.
    if (est.varredura) { encerrar(); recado('A varredura parou: a conexão com a Guarnição caiu.', true); carregar(); }
  };
}

function encerrar() {
  if (fonte) { fonte.close(); fonte = null; }
  est.varredura = null;
}

function terminar(fim) {
  const rotulo = est.varredura.rotulo;
  encerrar();
  const achou = fim.ameaca + fim.suspeito;
  recado(achou
    ? `Varredura ${rotulo.toLowerCase()} concluída: ${[fim.ameaca && plural(fim.ameaca, 'ameaça', 'ameaças'), fim.suspeito && plural(fim.suspeito, 'suspeito', 'suspeitos')].filter(Boolean).join(' e ')}`
    : `Varredura ${rotulo.toLowerCase()} concluída: ${plural(fim.total, 'arquivo', 'arquivos')}, tudo limpo`);
  carregar();
}

async function trancar(ids) {
  est.ocupado = true; desenhar();
  let trancados = 0; let erro = null;
  for (const id of ids) {
    try { await pedir('/api/isolar', { id }); trancados += 1; } catch (e) { erro = e.message; }
  }
  est.ocupado = false;
  if (trancados) {
    est.trancouAte = Date.now() + 4000;
    setTimeout(desenhar, 4100);
    recado(trancados === 1 ? 'Trancado na quarentena. Dá para devolver na aba Quarentena.' : `${trancados} arquivos trancados na quarentena.`);
  }
  if (erro) recado(`Não deu para trancar: ${erro}`, true);
  carregar();
}

async function cacar() {
  est.cacando = true; desenhar();
  try {
    const c = await pedir('/api/cacar');
    if (!c.achados.length) recado('O Vidente não achou nada escondido.');
  } catch (e) {
    recado(`A caçada falhou: ${e.message}`, true);
  }
  est.cacando = false;
  est.cacadaFechada = null;
  carregar();
}

async function atualizar() {
  est.ocupado = true; desenhar();
  try {
    const r = await pedir('/api/atualizar');
    const erros = r.bases.filter((b) => b.situacao === 'erro');
    recado(erros.length ? `Não deu para atualizar ${erros.map((b) => b.base).join(', ')}: ${erros[0].erro}` : 'Bases conferidas e em dia.', erros.length > 0);
  } catch (e) {
    recado(e.message, true);
  }
  est.ocupado = false;
  carregar();
}

async function escolherPasta() {
  try {
    const r = await pedir('/api/escolher-pasta');
    if (!r.cancelado) varrer('pasta', r.id, r.nome);
  } catch (e) {
    recado(`Não consegui abrir o seletor de pastas: ${e.message}`, true);
  }
}

document.addEventListener('click', (evento) => {
  const botao = evento.target.closest('[data-acao]');
  if (!botao || botao.disabled) return;
  const { acao } = botao.dataset;
  if (acao === 'varrer') varrer(botao.dataset.alvo);
  else if (acao === 'pasta') escolherPasta();
  else if (acao === 'parar') { encerrar(); recado('Varredura interrompida.'); carregar(); }
  else if (acao === 'trancar') trancar([botao.dataset.id]);
  else if (acao === 'trancar-todas') trancar(est.historico.pendentes.map((a) => a.id));
  else if (acao === 'cacar') cacar();
  else if (acao === 'fechar-cacada') { est.cacadaFechada = est.servidor.cacada.quando; desenhar(); }
  else if (acao === 'atualizar') atualizar();
  else if (acao === 'filtro') { abas.filtro = botao.dataset.filtro; abas.escrever = true; desenharHistorico(); }
  else if (acao === 'primeira') { location.hash = '#painel'; varrer('rapida'); }
  else if (acao === 'devolver') {
    mexerNaCela('/api/devolver', botao.dataset.id, (r) => `Devolvido para ${pastaCurta(r.caminho)}.`);
  } else if (acao === 'apagar') perguntarApagar(botao.dataset.id);
  else if (acao === 'fechar-modal') fecharModal();
  else if (acao === 'apagar-de-vez') mexerNaCela('/api/apagar', botao.dataset.id, () => 'Apagado de vez.');
  else if (acao === 'copiar') {
    navigator.clipboard.writeText(botao.dataset.texto)
      .then(() => recado('Comando copiado. Cole no terminal.'))
      .catch(() => recado('Não deu para copiar. Selecione o comando e copie à mão.', true));
  }
});

// ---- abas: Histórico (pergaminho) e Quarentena (cela) ----
const TINTA = { ok: '#2f6b45', perigo: '#9b2a1e', aviso: '#a1500b', '': '#9b2a1e', tinta: '#2e2012' };
const FILTROS = [
  ['todas', 'Todas', () => true],
  ['rapidas', 'Rápidas', (r) => r.tipo === 'rápida'],
  ['completas', 'Completas', (r) => r.tipo === 'completa'],
  ['pastas', 'Pastas', (r) => r.tipo !== 'rápida' && r.tipo !== 'completa'],
  ['achados', 'Com achados', (r) => r.ameacas || r.suspeitos],
];
const SELO_CERA = '<svg viewBox="0 0 74 74"><path d="M37 3 C46 2 50 7 57 9 C65 12 70 18 70 27 C72 35 68 40 70 47 C70 56 64 63 56 66 C49 70 44 72 37 71 C29 72 23 69 17 66 C9 62 4 55 4 46 C2 39 5 33 4 26 C5 17 11 11 19 8 C25 5 30 3 37 3 Z" fill="url(#hpCera)" stroke="#4a0a06" stroke-width="1"></path><circle cx="37" cy="37" r="24" fill="none" stroke="#5a0e08" stroke-width="2" opacity=".6"></circle><circle cx="37" cy="37" r="22" fill="none" stroke="#e07a5a" stroke-width=".8" opacity=".45"></circle><path d="M20 18 C24 14 30 12 36 12" fill="none" stroke="#ffb8a0" stroke-opacity=".5" stroke-width="2" stroke-linecap="round"></path></svg>';
const CORRENTE = (lado) => `<svg class="cq-corrente" style="${lado}: 16%" viewBox="0 0 12 42" aria-hidden="true"><g fill="none" stroke="#6b707c" stroke-width="2"><ellipse cx="6" cy="6" rx="4" ry="6"></ellipse><path d="M6 12 V24" stroke-width="3"></path><ellipse cx="6" cy="30" rx="4" ry="6"></ellipse><path d="M6 36 V42" stroke-width="3"></path></g></svg>`;
const CADEADO = '<svg class="cq-cadeado" viewBox="0 0 58 70" aria-hidden="true"><path class="cq-arco" d="M15 34 V22 a14 14 0 0 1 28 0 V34" fill="none" stroke="#8a909c" stroke-width="6" stroke-linecap="round"></path><path class="cq-arco" d="M15 34 V22 a14 14 0 0 1 28 0 V34" fill="none" stroke="#2a2c33" stroke-width="1.5" stroke-linecap="round"></path><rect x="6" y="32" width="46" height="34" rx="5" fill="#6b5a3a" stroke="#0b0c10" stroke-width="2"></rect><rect x="9" y="35" width="40" height="5" rx="2" fill="#a88a52" opacity=".7"></rect><path d="M29 44 a4 4 0 1 1 0.01 0 Z M27 47 H31 L32 57 H26 Z" fill="#0b0c10"></path></svg>';
const CHAVE = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="5" cy="9" r="3.6" fill="none" stroke="currentColor" stroke-width="1.8"></circle><path d="M8.6 9 H17 M14 9 V12 M16.4 9 V11.4" stroke="currentColor" stroke-width="1.8"></path></svg>';

const abas = { filtro: 'todas', escrever: true, quarentena: null, artePronta: {} };

function numeroCurto(n) {
  if (n < 1e6) return numero(n);
  const m = n / 1e6;
  return `${m.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} ${m < 2 ? 'milhão' : 'milhões'}`;
}

function duracao(s) {
  if (s == null) return '';
  if (s < 60) return `${s.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`;
  const min = Math.floor(s / 60);
  return min < 60 ? `${min} min ${Math.round(s % 60)} s` : `${Math.floor(min / 60)} h ${min % 60} min`;
}

function tamanho(bytes) {
  const unidades = ['B', 'KB', 'MB', 'GB'];
  let v = bytes || 0; let i = 0;
  while (v >= 1024 && i < unidades.length - 1) { v /= 1024; i += 1; }
  return `${v.toLocaleString('pt-BR', { maximumFractionDigits: i ? 1 : 0 })} ${unidades[i]}`;
}

function nomeDoDia(d) {
  const dias = Math.round((meiaNoite(new Date()) - meiaNoite(d)) / 864e5);
  if (dias === 0) return 'Hoje';
  if (dias === 1) return 'Ontem';
  const texto = dias < 7 ? d.toLocaleDateString('pt-BR', { weekday: 'long' })
    : d.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// "achada pelo Cavaleiro", "percebido pela Arqueira"...
function porQuem(camada, veredito) {
  if (!camada) return '';
  const p = PERSONAGENS.find((x) => x.quem === (DONO[camada] || 'vidente'));
  const [artigo, ...resto] = p.nome.split(' ');
  return `${veredito === 'ameaca' ? 'achada' : 'percebido'} ${artigo === 'A' ? 'pela' : 'pelo'} ${resto.join(' ')}`;
}
const maiuscula = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const pastaCurta = (caminho) => (caminho || '').split('/').slice(0, -1).join('/').replace(/^\/home\/[^/]+/, '~') || '/';

async function arte(nome, onde) {
  if (abas.artePronta[nome]) return;
  abas.artePronta[nome] = true;
  try { $(onde).innerHTML = await fetch(`/estatico/arte/${nome}.html`).then((r) => r.text()); } catch { abas.artePronta[nome] = false; }
}

function desenharHistorico() {
  const h = est.historico;
  if (!h) return;
  const regs = h.registros;
  const escrever = abas.escrever; abas.escrever = false;
  let n = 0;
  const pena = () => (escrever && n <= 10 ? ` hp-escreve" style="animation-name: hpE${n++}` : '');
  const item = (rot, val, cor) => `<div><dt>${esc(rot)}</dt><dd style="color: ${TINTA[cor]}">${esc(val)}</dd></div>`;

  if (!regs.length) {
    $('#hp-resumo').innerHTML = item('Primeira varredura', 'ainda não', 'tinta');
    $('#hp-registro').innerHTML = `<div class="hp-branco"><p>Ainda não há nada anotado aqui.</p>
      <p>Cada varredura que a Guarnição fizer vira uma linha deste registro, com a hora, o tipo e o que foi encontrado.</p>
      <div class="hp-linhas" aria-hidden="true"></div>
      <button type="button" data-acao="primeira">Fazer a primeira varredura</button></div>`;
    return;
  }
  const limite = Date.now() - 30 * 864e5;
  const mes = regs.filter((r) => paraData(r.inicio).getTime() >= limite);
  const ameacas = mes.reduce((s, r) => s + (r.ameacas || 0), 0);
  const soltas = h.pendentes.filter((a) => a.veredito === 'ameaca').length;
  $('#hp-resumo').innerHTML = item('Varreduras em 30 dias', numero(mes.length), 'tinta')
    + item('Arquivos verificados', numeroCurto(mes.reduce((s, r) => s + (r.total || 0), 0)), 'tinta')
    + item('Ameaças encontradas', numero(ameacas), ameacas ? 'perigo' : 'tinta')
    + (soltas ? item('Ainda soltas', numero(soltas), 'perigo') : item('Todas trancadas', '✓ Sim', 'ok'));

  const filtro = FILTROS.find((f) => f[0] === abas.filtro);
  const lista = regs.filter(filtro[2]);
  let html = `<div class="hp-filtros" role="group" aria-label="Filtrar">${FILTROS.map(([id, rot]) =>
    `<button type="button" data-acao="filtro" data-filtro="${id}" aria-pressed="${id === abas.filtro}">${rot}</button>`).join('')}</div>
    <section class="hp-razao" aria-label="Varreduras">`;
  let diaAntes = '';
  for (const r of lista) {
    const d = paraData(r.inicio);
    const dia = nomeDoDia(d);
    if (dia !== diaAntes) { html += `<div class="hp-dia${pena()}">${esc(dia)}</div>`; diaAntes = dia; }
    const res = resultado(r);
    const tipo = r.tipo === 'rápida' ? 'Varredura rápida' : r.tipo === 'completa' ? 'Varredura completa' : nomeDoTipo(r.tipo).replace('Pasta · ', 'Pasta ');
    const primeiro = r.achados.find((a) => a.veredito === 'ameaca') || r.achados[0];
    html += `<div class="hp-linha${pena()}">
      <span class="hp-hora">${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
      <div><div class="hp-tipo">${esc(tipo)}</div><div class="hp-meta">${esc([plural(r.total, 'arquivo', 'arquivos'), duracao(r.segundos)].filter(Boolean).join(' · '))}</div></div>
      <div><span class="hp-res" style="color: ${TINTA[res.cor]}">${esc(res.texto)}</span><span class="hp-quem">${esc(primeiro ? maiuscula(porQuem(primeiro.camada, primeiro.veredito)) : '')}</span></div>
    </div>`;
  }
  if (!lista.length) html += '<div class="hp-branco"><p>Nenhuma varredura deste tipo ainda.</p></div>';
  html += `</section><div class="hp-pe"><div class="hp-assina">Registrado pela Guarnição
    <div class="hp-selo" aria-hidden="true">${SELO_CERA}<div class="hp-selo-emb"><img src="/estatico/arte/emblema.svg" alt="" width="100%"></div></div></div></div>`;
  $('#hp-registro').innerHTML = html;
}

async function carregarQuarentena() {
  try {
    abas.quarentena = (await fetch('/api/quarentena').then((r) => r.json())).itens;
  } catch {
    recado('Não consegui ler a quarentena.', true);
  }
  desenharQuarentena();
}

function tracos(n) {
  // Riscos de giz na parede: grupos de cinco, o quinto cortando os outros.
  let svg = ''; const k = Math.min(n, 5);
  for (let i = 0; i < Math.min(k, 4); i += 1) svg += `M${6 + i * 6} 3 L${5 + i * 6} 27 `;
  if (k === 5) svg += 'M2 22 L30 8';
  return n ? `<svg width="34" height="30" viewBox="0 0 34 30" aria-hidden="true"><path d="${svg}" stroke="#e6e2d6" stroke-width="2.6" stroke-linecap="round" opacity=".85" fill="none"></path></svg>` : '';
}

function desenharQuarentena() {
  const itens = abas.quarentena;
  if (!itens) return;
  const giz = (rot, val, cor = '#e6e2d6', extra = '') => `<div><dt>${esc(rot)}</dt><dd style="color: ${cor}">${esc(val)}${extra}</dd></div>`;
  if (!itens.length) {
    $('#cq-giz').innerHTML = giz('Arquivos trancados', '0') + giz('Último trancado', 'nenhum') + giz('Podem rodar?', '✓ Nada aqui', '#9fdcb8');
    $('#cq-lista').innerHTML = `<section class="cq-vazia"><h2>A cela está vazia</h2>
      <p>Nada está trancado agora. Quando uma varredura achar algo perigoso, você escolhe se quer trancar aqui — e pode devolver depois, se for engano.</p></section>`;
    return;
  }
  const antigo = itens.map((i) => i.data).filter(Boolean).sort()[0];
  $('#cq-giz').innerHTML = giz('Arquivos trancados', numero(itens.length), '#e6e2d6', tracos(itens.length))
    + giz('Espaço ocupado', tamanho(itens.reduce((s, i) => s + (i.tamanho || 0), 0)))
    + giz('Mais antigo', antigo ? quando(antigo) : '—') + giz('Podem rodar?', '✓ Não', '#9fdcb8');
  $('#cq-lista').innerHTML = `<section aria-label="Arquivos trancados"><div class="cq-trave" aria-hidden="true"></div><div class="cq-placas">
    ${itens.map((i) => {
      const ameaca = i.veredito !== 'suspeito';
      const quem = porQuem(i.camada, i.veredito);
      return `<div class="cq-pendura">${CORRENTE('left')}${CORRENTE('right')}<article class="cq-placa">${CADEADO}
        <div class="cq-info"><span class="cq-carimbo" style="color: ${ameaca ? '#FF8A7A' : '#F0B65A'}">${ameaca ? 'Ameaça' : 'Suspeito'}</span>
        <span class="cq-etiqueta">${esc(i.nome)}</span>
        <span class="cq-dado">${esc([i.motivo, quem].filter(Boolean).join(' · '))}</span>
        <span class="cq-dado">Veio de <code>${esc(pastaCurta(i.original))}</code>${i.data ? ` · trancado ${esc(quando(i.data))}` : ''}</span></div>
        <div class="cq-acoes"><button type="button" class="cq-devolver" data-acao="devolver" data-id="${esc(i.id)}">${CHAVE}Devolver</button>
        <button type="button" class="cq-apagar" data-acao="apagar" data-id="${esc(i.id)}">Apagar</button></div></article></div>`;
    }).join('')}</div><p class="cq-aviso">Apagar remove o arquivo de vez. Não dá para desfazer.</p></section>`;
}

function perguntarApagar(id) {
  const item = (abas.quarentena || []).find((i) => i.id === id);
  if (!item) return;
  $('#cq-modal').innerHTML = `<div class="cq-modal"><div class="cq-dialogo" role="alertdialog" aria-modal="true" aria-labelledby="cq-pergunta">
    <h2 id="cq-pergunta">Apagar ${esc(item.nome)} de vez?</h2>
    <p>O arquivo sai da cela e é removido do computador. Não dá para desfazer.</p>
    <p>Se ele foi trancado por engano, use <strong>Devolver</strong> em vez de apagar.</p>
    <div class="cq-acoes"><button type="button" class="cq-devolver" data-acao="fechar-modal">Cancelar</button>
    <button type="button" class="cq-apagar-de-vez" data-acao="apagar-de-vez" data-id="${esc(id)}">Apagar de vez</button></div></div></div>`;
  $('#cq-modal [data-acao="fechar-modal"]').focus();
}
const fecharModal = () => { $('#cq-modal').innerHTML = ''; };

async function mexerNaCela(rota, id, feito) {
  try {
    const r = await pedir(rota, { id });
    recado(feito(r));
  } catch (e) {
    recado(`Não deu: ${e.message}`, true);
  }
  fecharModal();
  carregarQuarentena();
  carregar();
}

function rota() {
  const aba = { '#historico': 'historico', '#quarentena': 'quarentena' }[location.hash] || 'painel';
  $('#muralha').hidden = aba !== 'painel';
  $('#pergaminho').hidden = aba !== 'historico';
  $('#cela').hidden = aba !== 'quarentena';
  document.querySelectorAll('.gn-nav a').forEach((l) => {
    if (l.getAttribute('href') === `#${aba}`) l.setAttribute('aria-current', 'page'); else l.removeAttribute('aria-current');
  });
  fecharModal();
  if (aba === 'historico') {
    arte('pergaminho', '#arte-pergaminho');
    abas.escrever = true;
    desenharHistorico();
    document.title = 'Histórico · Guarnição';
  } else if (aba === 'quarentena') {
    arte('cela', '#cela-cena');
    carregarQuarentena();
    document.title = 'Quarentena · Guarnição';
  } else {
    desenhar();
  }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', rota);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && $('#cq-modal').innerHTML) fecharModal(); });

// ---- início ----
desenharEstrelas();
montarGuardioes().then(carregar).then(rota);
// O estado muda sozinho (serviços, varreduras agendadas): confere a cada minuto.
setInterval(() => { if (!est.varredura && !est.cacando && !est.ocupado) carregar(); }, 60000);
