import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {TOM, FRASE, botoes, curto, detalhe, retrato} from './regras.js';

const VERTICAL = Clutter.Orientation.VERTICAL;

// O cartão do avisos-v3: ameias no alto, faixa da cor do estado, retrato com a
// luz da tocha, textos e botões. Tudo texto puro (St.Label), nunca markup.
export function cartao({dados, titulo, corpo, pastaArte, aoClicar}) {
    if (curto(dados))
        return cartaoCurto({dados, titulo, corpo, pastaArte, aoClicar});
    const tom = TOM[dados.tipo] ?? '';
    const caixa = new St.BoxLayout({style_class: 'guarnicao-cartao', orientation: VERTICAL});
    caixa.add_child(new St.Widget({style_class: 'guarnicao-ameia', x_expand: true}));

    const miolo = new St.BoxLayout({style_class: `guarnicao-corpo ${tom}`, orientation: VERTICAL});
    caixa.add_child(miolo);
    const linha = new St.BoxLayout({style_class: 'guarnicao-linha'});
    miolo.add_child(linha);

    const quem = retrato(dados);
    if (quem) {
        const luz = new St.Bin({style_class: `guarnicao-luz ${tom}`});
        luz.set_child(new St.Widget({
            style_class: 'guarnicao-retrato',
            style: `background-image: url("file://${pastaArte}/${quem}.svg");`,
        }));
        linha.add_child(luz);
    }

    const textos = new St.BoxLayout({style_class: 'guarnicao-textos', orientation: VERTICAL, x_expand: true});
    linha.add_child(textos);
    const rotulo = (texto, classe) => {
        const l = new St.Label({text: texto, style_class: classe});
        l.clutter_text.line_wrap = true;
        l.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        textos.add_child(l);
    };
    rotulo('GUARNIÇÃO · AGORA', 'guarnicao-quem');
    rotulo(titulo, `guarnicao-titulo ${tom}`);
    if (dados.arquivo)
        rotulo(dados.arquivo, 'guarnicao-arquivo');
    const texto = detalhe(dados, corpo);
    if (texto)
        rotulo(texto, 'guarnicao-detalhe');
    if (FRASE[dados.tipo])
        rotulo(FRASE[dados.tipo], 'guarnicao-frase');

    const lista = botoes(dados);
    if (lista.length) {
        const fila = new St.BoxLayout({style_class: 'guarnicao-botoes', x_align: Clutter.ActorAlign.END});
        for (const b of lista) {
            const botao = new St.Button({
                label: b.rotulo, can_focus: true,
                style_class: `guarnicao-botao${b.principal ? ' principal' : ''}`,
            });
            botao.connect('clicked', () => aoClicar(b.args));
            fila.add_child(botao);
        }
        miolo.add_child(fila);
    }
    return caixa;
}

// Limpa e trancado (avisos-v3): uma faixa com o emblema, o título e uma linha;
// o trancado tem o Desfazer à direita, discreto.
function cartaoCurto({dados, titulo, corpo, pastaArte, aoClicar}) {
    const caixa = new St.BoxLayout({style_class: 'guarnicao-cartao curto', orientation: VERTICAL});
    caixa.add_child(new St.Widget({style_class: 'guarnicao-ameia', x_expand: true}));
    const linha = new St.BoxLayout({style_class: 'guarnicao-corpo curto'});
    caixa.add_child(linha);
    linha.add_child(new St.Widget({
        style_class: 'guarnicao-emblema', y_align: Clutter.ActorAlign.CENTER,
        style: `background-image: url("file://${pastaArte}/emblema.svg");`,
    }));
    const textos = new St.BoxLayout({style_class: 'guarnicao-textos', orientation: VERTICAL, x_expand: true,
        y_align: Clutter.ActorAlign.CENTER});
    linha.add_child(textos);
    textos.add_child(new St.Label({text: titulo, style_class: 'guarnicao-titulo curto'}));
    const segunda = dados.tipo === 'trancado'
        ? new St.Label({text: dados.arquivo ?? '', style_class: 'guarnicao-arquivo curto'})
        : new St.Label({text: detalhe(dados, corpo), style_class: 'guarnicao-limpo'});
    segunda.clutter_text.ellipsize = Pango.EllipsizeMode.END;
    textos.add_child(segunda);
    for (const b of botoes(dados)) {
        const botao = new St.Button({label: b.rotulo, can_focus: true, style_class: 'guarnicao-desfazer',
            y_align: Clutter.ActorAlign.CENTER});
        botao.connect('clicked', () => aoClicar(b.args));
        linha.add_child(botao);
    }
    return caixa;
}
