import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Vinculos} from '../guarnicao@eduardomilani8.github.io/vinculo.js';

// Um daemon de mentira com o mesmo jeito do notificationDaemon.js do GNOME 50:
// um Map id → notificação e o próximo id a usar.
function daemonFalso() {
    const d = {_notifications: new Map(), _nextNotificationId: 1};
    d.notificar = replacesId => {
        if (replacesId !== 0 && d._notifications.has(replacesId))
            return d._notifications.get(replacesId);
        const n = {id: d._nextNotificationId++};
        d._notifications.set(n.id, n);
        return n;
    };
    return d;
}

test('dois avisos com o mesmo texto ficam cada um com os seus dados', () => {
    const d = daemonFalso();
    const v = new Vinculos(d);
    v.guardar(0, {quarentena: 'aaa'});
    const n1 = d.notificar(0);
    v.guardar(0, {quarentena: 'bbb'});
    const n2 = d.notificar(0);
    assert.deepEqual(v.tirar(n1), {quarentena: 'aaa'});
    assert.deepEqual(v.tirar(n2), {quarentena: 'bbb'});
    assert.equal(v.tirar(n1), null);
});

test('um aviso que substitui outro fica com os dados novos', () => {
    const d = daemonFalso();
    const v = new Vinculos(d);
    v.guardar(0, {tipo: 'ameaca'});
    const n = d.notificar(0);
    v.guardar(n.id, {tipo: 'trancado'});
    assert.equal(d.notificar(n.id), n);
    assert.deepEqual(v.tirar(n), {tipo: 'trancado'});
});

test('aviso de outro app não pega dados de ninguém', () => {
    const d = daemonFalso();
    const v = new Vinculos(d);
    const outro = d.notificar(0);
    v.guardar(0, {tipo: 'ameaca'});
    d.notificar(0);
    assert.equal(v.tirar(outro), null);
});

test('não guarda mais que 20', () => {
    const d = daemonFalso();
    const v = new Vinculos(d);
    const ns = [];
    for (let i = 0; i < 25; i++) {
        v.guardar(0, {i: String(i)});
        ns.push(d.notificar(0));
    }
    assert.equal(v.tirar(ns[0]), null);
    assert.deepEqual(v.tirar(ns[24]), {i: '24'});
});

test('reconhece um daemon que não tem o jeito esperado', () => {
    assert.equal(Vinculos.serve({_notifications: new Map(), _nextNotificationId: 1}), true);
    assert.equal(Vinculos.serve({_notifications: {}, _nextNotificationId: 1}), false);
    assert.equal(Vinculos.serve(undefined), false);
});
