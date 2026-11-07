// Prende os dados escondidos de um aviso ao próprio aviso, pelo id que o GNOME
// dá a ele, e não pelo texto: dois "Trancado na quarentena" de x.exe em pastas
// diferentes têm o mesmo texto, e o Desfazer de um não pode restaurar o outro.
// Sem GNOME aqui, para testar com node --test.

const MAXIMO = 20;

export class Vinculos {
    // O jeito do notificationDaemon.js do GNOME 50. Se mudar, plano B.
    static serve(daemon) {
        return daemon?._notifications instanceof Map && Number.isInteger(daemon?._nextNotificationId);
    }

    constructor(daemon) {
        this._daemon = daemon;
        this._dados = new Map();
    }

    // Chamado antes do NotifyAsync original: o id é o que ele vai usar.
    guardar(replacesId, dados) {
        const d = this._daemon;
        const id = replacesId !== 0 && d._notifications.has(replacesId) ? replacesId : d._nextNotificationId;
        this._dados.delete(id);
        this._dados.set(id, dados);
        if (this._dados.size > MAXIMO)
            this._dados.delete(this._dados.keys().next().value);
    }

    // Os dados desta notificação (uma vez só), ou null se não é da Guarnição.
    tirar(notificacao) {
        for (const [id, n] of this._daemon._notifications) {
            if (n === notificacao && this._dados.has(id)) {
                const dados = this._dados.get(id);
                this._dados.delete(id);
                return dados;
            }
        }
        return null;
    }

    limpar() {
        this._dados.clear();
    }
}
