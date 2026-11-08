// Regras puras dos avisos e do escudo: sem GNOME aqui, para testar com node --test.

export const NOMES = {cavaleiro: 'Cavaleiro', arqueira: 'Arqueira', vidente: 'Vidente', carcereiro: 'Carcereiro'};

// Cor do estado no cartão (avisos-v3): perigo = vermelho, atenção = âmbar, o resto sem faixa colorida.
export const TOM = {ameaca: 'perigo', varias: 'perigo', bloqueado: 'perigo', suspeito: 'atencao', bases: 'atencao'};

export const FRASE = {
    ameaca: 'O Carcereiro aguarda sua ordem.',
    varias: 'O Carcereiro aguarda sua ordem.',
    suspeito: 'O Vidente percebeu algo estranho.',
    bloqueado: 'O protetor impediu que ele rodasse.',
    bases: 'Sem bases novas, o Cavaleiro não reconhece ameaças recentes.',
    semanal: 'Ela anda devagar e cede a vez a jogos e ao que estiver aberto.',
};

export const ROTULOS_MENU = {
    varrer: 'Varredura rápida', abrir: 'Abrir painel', trancar: 'Abrir painel e trancar',
    atualizar: 'Atualizar agora', parar: 'Parar varredura',
};

// Com problema, a ação que resolve vem primeiro, num botão dourado (barra-v2).
export function acaoPrincipal(estado) {
    return estado === 'atencao' || estado === 'ameaca';
}

export const COMANDOS_MENU = {
    varrer: ['varrer', '--rapida', '--agendada'], abrir: ['launcher'], trancar: ['launcher'],
    atualizar: ['atualizar'], parar: ['varrer', '--parar'],
};

// Só os hints x-guarnicao-*, e só se forem texto. Nada é interpretado.
export function lerDados(hints) {
    const dados = {};
    for (const [chave, valor] of Object.entries(hints ?? {})) {
        if (chave.startsWith('x-guarnicao-') && typeof valor === 'string')
            dados[chave.slice('x-guarnicao-'.length)] = valor;
    }
    return dados.tipo ? dados : null;
}

// "Quem aparece é quem vai agir" (avisos-v3): ameaça é do Carcereiro, que tranca;
// suspeito, do Vidente; bases, do Cavaleiro. O bloqueio já foi feito por quem achou.
const QUEM_AGE = {ameaca: 'carcereiro', varias: 'carcereiro', trancado: 'carcereiro',
    suspeito: 'vidente', bases: 'cavaleiro'};

// Os que só confirmam (avisos-v3): uma faixa curta com o emblema, sem retrato nem frase.
export function curto(dados) {
    return dados.tipo === 'limpa' || dados.tipo === 'trancado';
}

export function retrato(dados) {
    const nome = QUEM_AGE[dados.tipo] ?? dados.personagem;
    return NOMES[nome] ? nome : null;
}

const PELO = {cavaleiro: 'pelo Cavaleiro', arqueira: 'pela Arqueira', vidente: 'pelo Vidente'};

// Quando há arquivo, a primeira linha do corpo é o nome dele: o cartão já mostra em fonte mono.
// Na ameaça, quem reconheceu vem antes (o retrato é do Carcereiro).
export function detalhe(dados, corpo) {
    const linhas = (corpo ?? '').split('\n').map(l => l.trim()).filter(Boolean);
    const partes = dados.arquivo ? linhas.slice(1) : linhas;
    if (dados.tipo === 'ameaca' && PELO[dados.personagem])
        partes.unshift(`Reconhecida ${PELO[dados.personagem]}`);
    return partes.join(' · ');
}

// Os botões de cada aviso, na ordem do avisos-v3 (o dourado por último).
export function botoes(dados) {
    const painel = rotulo => ({rotulo, args: ['launcher']});
    const trancar = dados.caminho && dados.sha256
        ? [{rotulo: 'Trancar', args: ['quarentena', 'trancar', dados.caminho, '--sha256', dados.sha256], principal: true}]
        : [];
    switch (dados.tipo) {
    case 'ameaca': return [painel('Abrir painel'), ...trancar];
    case 'suspeito': return [painel('Ver detalhes'), ...trancar];
    case 'varias': return [painel('Ver o que foi achado'), {rotulo: 'Trancar todas', args: ['launcher'], principal: true}];
    case 'bases': return [painel('Abrir painel'), {rotulo: 'Atualizar agora', args: ['atualizar'], principal: true}];
    case 'bloqueado': return [painel('Abrir painel')];
    case 'semanal': return [{rotulo: 'Mais tarde', args: []}, {rotulo: 'Varrer agora', args: ['semanal', '--agora'], principal: true}];
    case 'trancado': return dados.quarentena ? [{rotulo: 'Desfazer', args: ['quarentena', 'restaurar', dados.quarentena]}] : [];
    default: return [];
    }
}
