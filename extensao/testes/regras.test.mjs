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
