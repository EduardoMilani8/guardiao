import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {cartao} from './cartao.js';
import {lerDados} from './regras.js';
import {Vinculos} from './vinculo.js';

const APP = 'Guarnição';

// Os avisos chegam pelo notify-send como sempre. Aqui guardamos os dados
// escondidos (hints x-guarnicao-*) e, quando o GNOME monta o balão, trocamos o
// recheio pelo cartão da muralha. Posição, tempo e foco continuam com o GNOME.
export class Avisos {
    constructor(pastaArte, comandos, aoChegar) {
        this._pastaArte = pastaArte;
        this._comandos = comandos;
        this._aoChegar = aoChegar;
    }

    ligar() {
        const daemon = Main.notificationDaemon?._fdoNotificationDaemon;
        const tray = Main.messageTray;
        // Plano B: se o GNOME mudou por dentro, não mexemos nos avisos (ficam os comuns).
        if (typeof daemon?.NotifyAsync !== 'function' || typeof tray?._showNotification !== 'function' ||
            !Vinculos.serve(daemon)) {
            console.warn('Guarnição: esta versão do GNOME não deixa trocar o desenho dos avisos');
            return false;
        }
        const avisos = this;
        this._daemon = daemon;
        this._tray = tray;
        this._vinculos = new Vinculos(daemon);
        this._notifyOriginal = daemon.NotifyAsync;
        this._mostrarOriginal = tray._showNotification;
        daemon.NotifyAsync = function (params, invocation) {
            try {
                avisos._guardar(params);
            } catch (e) {
                logError(e, 'Guarnição: não deu para ler o aviso');
            }
            return avisos._notifyOriginal.call(this, params, invocation);
        };
        tray._showNotification = function () {
            avisos._mostrarOriginal.call(this);
            try {
                avisos._vestir(this);
            } catch (e) {
                logError(e, 'Guarnição: não deu para desenhar o cartão');   // fica o balão comum
            }
        };
        return true;
    }

    desligar() {
        if (!this._daemon)
            return;
        this._daemon.NotifyAsync = this._notifyOriginal;
        this._tray._showNotification = this._mostrarOriginal;
        this._tray.bannerAlignment = Clutter.ActorAlign.CENTER;
        this._vinculos.limpar();
        this._daemon = this._tray = this._vinculos = null;
    }

    _guardar(params) {
        const [app, replacesId, , , , , hints] = params;
        if (app !== APP)
            return;
        const simples = {};
        for (const [k, v] of Object.entries(hints ?? {}))
            simples[k] = typeof v?.deepUnpack === 'function' ? v.deepUnpack() : v;
        this._aoChegar();
        const dados = lerDados(simples);
        if (!dados)
            return;
        this._vinculos.guardar(replacesId, dados);
    }

    _vestir(tray) {
        const n = tray._notification;
        const dados = n ? this._vinculos.tirar(n) : null;
        // Os da Guarnição aparecem no canto superior direito (avisos-v3); os outros, no meio.
        tray.bannerAlignment = dados ? Clutter.ActorAlign.END : Clutter.ActorAlign.CENTER;
        if (!dados)
            return;
        const banner = tray._banner;
        banner.set_child(cartao({
            dados, titulo: n.title, corpo: n.body ?? '', pastaArte: this._pastaArte,
            aoClicar: args => {
                this._comandos.rodar(args);
                n.destroy();
            },
        }));
        banner.style_class = 'guarnicao-banner';
    }
}
