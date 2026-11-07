import {test} from 'node:test';
import assert from 'node:assert/strict';
import {lerDados, detalhe, botoes, ROTULOS_MENU, COMANDOS_MENU} from '../guarnicao@eduardomilani8.github.io/regras.js';

test('só os hints da Guarnição, sempre como texto', () => {
    const d = lerDados({'x-guarnicao-tipo': 'ameaca', 'x-guarnicao-arquivo': '<b>$(rm -rf ~)</b>', urgency: 2});
    assert.deepEqual(d, {tipo: 'ameaca', arquivo: '<b>$(rm -rf ~)</b>'});
    assert.equal(lerDados({urgency: 1}), null);
});

test('o detalhe pula a linha do nome do arquivo', () => {
    assert.equal(detalhe({arquivo: 'x.exe'}, 'x.exe\nEICAR\nbaixado agora'), 'EICAR · baixado agora');
    assert.equal(detalhe({}, '305 arquivos, tudo limpo'), '305 arquivos, tudo limpo');
});

test('Trancar só com caminho e hash', () => {
    const com = botoes({tipo: 'ameaca', caminho: '/a/x.exe', sha256: 'ab'});
    assert.deepEqual(com.map(b => b.rotulo), ['Abrir painel', 'Trancar']);
    assert.deepEqual(com[1].args, ['quarentena', 'trancar', '/a/x.exe', '--sha256', 'ab']);
    assert.deepEqual(botoes({tipo: 'ameaca'}).map(b => b.rotulo), ['Abrir painel']);
    assert.deepEqual(botoes({tipo: 'trancado', quarentena: 'id1'})[0].args, ['quarentena', 'restaurar', 'id1']);
    assert.deepEqual(botoes({tipo: 'limpa'}), []);
});

test('toda ação do escudo tem rótulo e comando', () => {
    for (const acao of ['varrer', 'abrir', 'trancar', 'atualizar', 'parar']) {
        assert.ok(ROTULOS_MENU[acao] && COMANDOS_MENU[acao], acao);
    }
});

test('quem aparece é quem vai agir (avisos-v3)', async () => {
    const {retrato} = await import('../guarnicao@eduardomilani8.github.io/regras.js');
    assert.equal(retrato({tipo: 'ameaca', personagem: 'cavaleiro'}), 'carcereiro');
    assert.equal(retrato({tipo: 'varias'}), 'carcereiro');
    assert.equal(retrato({tipo: 'trancado', personagem: 'carcereiro'}), 'carcereiro');
    assert.equal(retrato({tipo: 'suspeito', personagem: 'vidente'}), 'vidente');
    assert.equal(retrato({tipo: 'bases', personagem: 'cavaleiro'}), 'cavaleiro');
    assert.equal(retrato({tipo: 'bloqueado', personagem: 'arqueira'}), 'arqueira');
    assert.equal(retrato({tipo: 'limpa', personagem: ''}), null);
});

test('na ameaça o detalhe diz quem reconheceu', () => {
    assert.equal(detalhe({tipo: 'ameaca', arquivo: 'x.exe', personagem: 'cavaleiro'}, 'x.exe\nEICAR'),
        'Reconhecida pelo Cavaleiro · EICAR');
    assert.equal(detalhe({tipo: 'ameaca', arquivo: 'x.exe', personagem: 'arqueira'}, 'x.exe\nRegra (YARA)'),
        'Reconhecida pela Arqueira · Regra (YARA)');
    assert.equal(detalhe({tipo: 'suspeito', arquivo: 'x.sh', personagem: 'vidente'}, 'x.sh\nbaixa script'),
        'baixa script');
});

test('limpa e trancado são avisos curtos, sem retrato (avisos-v3)', async () => {
    const {curto} = await import('../guarnicao@eduardomilani8.github.io/regras.js');
    assert.equal(curto({tipo: 'limpa'}), true);
    assert.equal(curto({tipo: 'trancado'}), true);
    assert.equal(curto({tipo: 'ameaca'}), false);
});

test('botão dourado só quando há problema (barra-v2)', async () => {
    const {acaoPrincipal} = await import('../guarnicao@eduardomilani8.github.io/regras.js');
    assert.equal(acaoPrincipal('atencao'), true);
    assert.equal(acaoPrincipal('ameaca'), true);
    assert.equal(acaoPrincipal('procurando'), false);
    assert.equal(acaoPrincipal('certo'), false);
});
