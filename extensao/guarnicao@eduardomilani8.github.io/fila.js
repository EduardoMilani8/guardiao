// Junta pedidos de atualização: vários em sequência viram um só, e um pedido que
// chega enquanto outro roda não se perde (roda mais uma vez no fim). Assim o fim
// de uma varredura nunca fica de fora e o escudo não abre Python sem parar.
// Sem GNOME aqui: quem chama passa como agendar (GLib no escudo, falso nos testes).

export class Fila {
    constructor(fn, {espera, agendar, aoErrar = e => console.error(e)}) {
        this._fn = fn;
        this._espera = espera;
        this._agendar = agendar;
        this._aoErrar = aoErrar;
        this._agendado = false;
        this._rodando = false;
        this._pendente = false;
    }

    pedir() {
        if (this._rodando) {
            this._pendente = true;
            return;
        }
        if (this._agendado)
            return;
        this._agendado = true;
        this._agendar(this._espera, () => this._rodar());
    }

    async _rodar() {
        this._agendado = false;
        this._rodando = true;
        try {
            await this._fn();
        } catch (e) {
            this._aoErrar(e);
        } finally {
            this._rodando = false;
        }
        if (this._pendente) {
            this._pendente = false;
            this.pedir();
        }
    }
}
