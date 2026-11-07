class Component extends DCLogic {
  renderVals() {
    const estado = this.props.estado ?? 'repouso';
    // cores do tema escuro (as mesmas do painel aprovado)
    const ok = '#8FD3B0', warn = '#F0B65A', danger = '#FF8A7A', goldText = '#E3C384', text = '#F3EEE2', text2 = '#B7BCCB';
    // tintas para o que é escrito em papel (mesa de guerra)
    const tinta = '#2e2012', tVerde = '#2f6b45', tSangue = '#9b2a1e', tAmbar = '#a1500b', tOuro = '#8a6420';
    // destaque de cada personagem: n normal, a agindo, p achou ameaça, w aviso, z fora da vez
    const estilo = {
      n: { filtro: 'none', op: '1', acesa: false, borda: 'rgba(90,60,25,.45)', bw: '1px', pino: '#8a6a3a' },
      a: { filtro: 'drop-shadow(0 0 16px rgba(212,175,106,.85))', op: '1', acesa: true, borda: tOuro, bw: '3px', pino: '#c9a24a' },
      p: { filtro: 'drop-shadow(0 0 18px rgba(255,90,70,.9))', op: '1', acesa: true, borda: tSangue, bw: '3px', pino: '#b8321f' },
      w: { filtro: 'drop-shadow(0 0 16px rgba(240,182,90,.85))', op: '1', acesa: true, borda: tAmbar, bw: '3px', pino: '#d9861c' },
      z: { filtro: 'grayscale(1)', op: '0.5', acesa: false, borda: 'rgba(90,60,25,.35)', bw: '1px', pino: '#7a7268' }
    };
    const destaques = { repouso: 'nnnn', varrendo: 'aaaz', ameaca: 'pzwa', atencao: 'wnnn', cacada: 'zzpz', parcial: 'nnnn', protetor: 'nnnn' }[estado];
    const base = [
      { nome: 'O Cavaleiro', papel: 'ASSINATURAS', quem: 'cavaleiro', faz: 'Reconhece ameaças já conhecidas pela base do ClamAV.' },
      { nome: 'A Arqueira', papel: 'REGRAS', quem: 'arqueira', faz: 'Mira nos padrões que denunciam famílias de malware.' },
      { nome: 'O Vidente', papel: 'SINAIS SUSPEITOS', quem: 'vidente', faz: 'Percebe comportamento de invasor, mesmo sem assinatura.' },
      { nome: 'O Carcereiro', papel: 'QUARENTENA', quem: 'carcereiro', faz: 'Tranca o que você mandar. Dá para devolver depois.' }
    ];
    const giro = [-2.4, 1.6, -1.2, 2.1];
    const camadas = base.map((b, i) => {
      const e = estilo[destaques[i]];
      return { ...b, ...e, apagada: !e.acesa, giro: giro[i] };
    });
    const titulo = {
      repouso: { texto: 'Você está protegido', cor: text, tc: tinta },
      varrendo: { texto: 'Procurando ameaças…', cor: text, tc: tinta },
      ameaca: { texto: '2 arquivos perigosos', cor: danger, tc: tSangue },
      atencao: { texto: 'Suas bases estão desatualizadas', cor: warn, tc: tAmbar },
      cacada: { texto: 'O Vidente achou 2 sinais de invasão', cor: danger, tc: tSangue },
      parcial: { texto: 'Tudo limpo no que deu para ler', cor: text, tc: tinta },
      protetor: { texto: 'O Protetor está desligado', cor: warn, tc: tAmbar }
    }[estado];
    const r = (rot, val, cor, tc) => ({ rot, val, cor, tc });
    const resumo = {
      repouso: [r('Última varredura', 'Rápida · hoje, 12:30', text, tinta), r('Arquivos verificados', '305', text, tinta), r('Resultado', '✓ Tudo limpo', ok, tVerde), r('Bases de ameaças', 'Atualizadas há 3 min', text, tinta)],
      varrendo: [r('Varredura', 'Rápida', text, tinta), r('Arquivos', '183 de 305', text, tinta), r('Andamento', '60%', goldText, tOuro), r('Encontrados', 'Nada até agora', ok, tVerde)],
      ameaca: [r('Ameaças', '1', danger, tSangue), r('Suspeitos', '1', warn, tAmbar), r('Varredura', 'Rápida · hoje, 12:30', text, tinta), r('Arquivos verificados', '305', text, tinta)],
      atencao: [r('Última atualização', 'Há 3 dias', warn, tAmbar), r('Serviço das bases', 'Parado', warn, tAmbar), r('Outras camadas', '✓ De guarda', ok, tVerde), r('Última varredura', 'Hoje, 12:30', text, tinta)],
      cacada: [r('Caçada', 'Hoje, 12:40', text, tinta), r('Sinais graves', '1', danger, tSangue), r('Sinais médios', '1', warn, tAmbar), r('O que mudou', 'Nada: só mostra', text, tinta)],
      parcial: [r('Última varredura', 'Completa · hoje, 10:15', text, tinta), r('Arquivos verificados', '412.508', text, tinta), r('Resultado', '✓ Tudo limpo', ok, tVerde), r('Ficaram de fora', '12 sem permissão', warn, tAmbar)],
      protetor: [r('Protetor', 'Desligado', warn, tAmbar), r('Desde', 'Hoje, 09:14', warn, tAmbar), r('Outras camadas', '✓ De guarda', ok, tVerde), r('Última varredura', 'Hoje, 12:30', text, tinta)]
    }[estado];
    const achados = [
      { tipo: 'Ameaça', cor: danger, tc: tSangue, arquivo: 'fatura-novembro.pdf.exe', detalhe: 'Reconhecida pelo Cavaleiro · ~/Downloads' },
      { tipo: 'Suspeito', cor: warn, tc: tAmbar, arquivo: 'atualizador-sistema.sh', detalhe: 'Age como minerador de criptomoeda · percebido pelo Vidente · ~/.local/bin' }
    ];
    const sinais = [
      { grav: 'Grave', cor: danger, tc: tSangue, onde: 'Serviço que inicia sozinho', arquivo: '~/.config/systemd/user/atualizador.service', msg: 'Roda /tmp/.x/kworker a cada login e não veio de nenhum pacote.' },
      { grav: 'Médio', cor: warn, tc: tAmbar, onde: 'Linha no ~/.bashrc', arquivo: '~/.bashrc · linha 118', msg: 'Troca o comando sudo por outro programa, que pode capturar a sua senha.' }
    ];
    const bases = estado === 'atencao'
      ? { nome: 'Atualização das bases', desc: 'Serviço parado desde segunda', st: 'há 3 dias', cor: warn, tc: tAmbar }
      : { nome: 'Atualização das bases', desc: 'De hora em hora · próxima às 13:00', st: 'há 3 min', cor: text2, tc: '#6b5236' };
    const fundo = [
      estado === 'protetor'
        ? { nome: 'Protetor', desc: 'Parado desde hoje, 09:14', st: 'Desligado', cor: warn, tc: tAmbar }
        : { nome: 'Protetor', desc: 'Analisa cada programa ao ser executado', st: 'Ligado', cor: ok, tc: tVerde },
      { nome: 'Monitor', desc: 'Downloads concluídos e processos estranhos', st: 'Ligado', cor: ok, tc: tVerde },
      bases,
      { nome: 'Varreduras agendadas', desc: 'Rápida todo dia · completa aos domingos', st: 'amanhã 12:30', cor: text2, tc: '#6b5236' }
    ];
    const ultimas = [
      estado === 'ameaca'
        ? { tipo: 'Rápida', quando: 'hoje, 12:30', arquivos: '305', resultado: '1 ameaça · 1 suspeito', cor: danger, tc: tSangue }
        : estado === 'parcial'
          ? { tipo: 'Completa', quando: 'hoje, 10:15', arquivos: '412.508', resultado: '✓ Limpo · 12 de fora', cor: ok, tc: tVerde }
          : { tipo: 'Rápida', quando: 'hoje, 12:30', arquivos: '305', resultado: '✓ Tudo limpo', cor: ok, tc: tVerde },
      { tipo: 'Pasta · Downloads', quando: 'ontem, 18:04', arquivos: '42', resultado: '1 ameaça · trancada', cor: text, tc: tinta },
      { tipo: 'Rápida', quando: 'ontem, 12:30', arquivos: '305', resultado: '✓ Tudo limpo', cor: ok, tc: tVerde }
    ];
    // estrelas do céu da muralha: posições fixas (sempre as mesmas), algumas piscam
    let semente = 7;
    const sorteio = () => { semente = (semente * 9301 + 49297) % 233280; return semente / 233280; };
    const estrelas = Array.from({ length: 90 }, (_, k) => ({
      x: Math.round(sorteio() * 1280), y: Math.round(sorteio() * 470), r: (0.5 + sorteio() * 1.3).toFixed(2),
      o: (0.35 + sorteio() * 0.6).toFixed(2), cls: k % 3 === 0 ? 'mu-pisca' : '', d: (sorteio() * 4).toFixed(2)
    }));
    // o céu muda com o estado
    const ceu = {
      repouso: { horizonte: 'rgba(90,120,180,.28)', lua: '#fffbe8', vento: 3.2 },
      varrendo: { horizonte: 'rgba(212,175,106,.24)', lua: '#fffbe8', vento: 1.6 },
      ameaca: { horizonte: 'rgba(255,80,50,.55)', lua: '#ffd9c8', vento: 1.1 },
      atencao: { horizonte: 'rgba(240,182,90,.32)', lua: '#fff3d6', vento: 2.4 },
      cacada: { horizonte: 'rgba(150,110,255,.38)', lua: '#ece4ff', vento: 1.8 },
      parcial: { horizonte: 'rgba(90,120,180,.28)', lua: '#fffbe8', vento: 3.2 },
      protetor: { horizonte: 'rgba(240,182,90,.32)', lua: '#fff3d6', vento: 2.4 }
    }[estado];
    // folhas do mapa: em que pasta cada estado deixa marca
    return {
      titulo, resumo, camadas, achados, sinais, fundo, ultimas, estrelas, ...ceu,
      isCacada: estado === 'cacada', isParcial: estado === 'parcial', isProtetor: estado === 'protetor',
      temAcoes: ['repouso', 'parcial', 'protetor'].includes(estado),
      isRepouso: estado === 'repouso', isVarrendo: estado === 'varrendo', isAmeaca: estado === 'ameaca', isAtencao: estado === 'atencao',
      fogo: estado === 'ameaca', fumaca: estado === 'atencao' || estado === 'protetor', brasa: estado === 'varrendo' || estado === 'cacada'
    };
  }
}
