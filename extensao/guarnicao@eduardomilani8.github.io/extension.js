import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {Avisos} from './avisos.js';
import {Comandos} from './comandos.js';
import {Escudo} from './escudo.js';

export default class Guarnicao extends Extension {
    enable() {
        this._comandos = new Comandos(this.path);
        this._escudo = new Escudo(this.path, this._comandos);
        Main.panel.addToStatusArea(this.uuid, this._escudo);
        this._avisos = new Avisos(`${this.path}/arte`, this._comandos, () => this._escudo?.atualizar());
        this._avisos.ligar();
    }

    disable() {
        this._avisos?.desligar();
        this._avisos = null;
        this._escudo?.destroy();
        this._escudo = null;
        this._comandos = null;
    }
}
