import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Fila} from '../guarnicao@eduardomilani8.github.io/fila.js';

// Relógio de mentira: agendar guarda a função; avancar() roda o que venceu.
function relogio() {
    let agora = 0;
    const timers = [];
    return {
        agendar: (ms, fn) => timers.push({quando: agora + ms, fn}),
        async avancar(ms) {
            agora += ms;
            for (;;) {
                const i = timers.findIndex(t => t.quando <= agora);
                if (i < 0)
                    break;
                const [t] = timers.splice(i, 1);
                t.fn();             // como o GLib: dispara e não espera
            }
            await new Promise(ok => setImmediate(ok));
        },
    };
}

test('vários pedidos seguidos viram uma atualização só', async () => {
    const r = relogio();
    let vezes = 0;
    const f = new Fila(async () => { vezes++; }, {espera: 1000, agendar: r.agendar});
    for (let i = 0; i < 10; i++)
        f.pedir();
    await r.avancar(1000);
    assert.equal(vezes, 1);
});

test('um pedido que chega durante a atualização não se perde', async () => {
    const r = relogio();
    let vezes = 0;
    let soltar;
    const f = new Fila(() => { vezes++; return vezes === 1 ? new Promise(ok => { soltar = ok; }) : null; },
        {espera: 1000, agendar: r.agendar});
    f.pedir();
    await r.avancar(1000);          // a primeira começa e fica rodando
    f.pedir();                      // o fim da varredura chega agora
    soltar();
    await new Promise(ok => setImmediate(ok));
    await r.avancar(1000);
    assert.equal(vezes, 2);
});

test('um erro não trava a fila', async () => {
    const r = relogio();
    let vezes = 0;
    const f = new Fila(async () => { vezes++; throw new Error('x'); }, {espera: 10, agendar: r.agendar, aoErrar: () => {}});
    f.pedir();
    await r.avancar(10);
    f.pedir();
    await r.avancar(10);
    assert.equal(vezes, 2);
});
