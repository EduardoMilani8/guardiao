import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {Fila} from './fila.js';
import {ROTULOS_MENU, COMANDOS_MENU} from './regras.js';

// O escudo da barra (barra-v2): o estado se lê pela forma, a cor só aparece no menu.
export const Escudo = GObject.registerClass(
class Escudo extends PanelMenu.Button {
    _init(pasta, comandos) {
        super._init(0.5, 'Guarnição');
        this._pasta = pasta;
        this._comandos = comandos;
        this._icone = new St.Icon({style_class: 'system-status-icon'});
        this.add_child(this._icone);
        this._mostrar({estado: 'certo', titulo: 'Guarnição', linhas: ['Conferindo…'], acoes: []});
        // Junta os pedidos (o andamento muda a cada segundo numa varredura) e
        // nunca perde o último, que é o fim da varredura.
        this._fila = new Fila(() => this._ler(), {
            espera: 1500,
            agendar: (ms, fn) => {
                this._agendado = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
                    this._agendado = 0;
                    fn();
                    return GLib.SOURCE_REMOVE;
                });
            },
            aoErrar: e => logError(e, 'Guarnição: não deu para ler o estado'),
        });

        this._relogio = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            this.atualizar();
            return GLib.SOURCE_CONTINUE;
        });
        const andamento = Gio.File.new_for_path(
            GLib.build_filenamev([GLib.get_user_cache_dir(), 'guarnicao', 'progresso.json']));
        this._vigia = andamento.monitor_file(Gio.FileMonitorFlags.NONE, null);
        this._vigia.connect('changed', () => this.atualizar());
        this.atualizar();
    }

    atualizar() {
        this._fila.pedir();
    }

    async _ler() {
        const estado = await this._comandos.json(['estado', '--json']);
        if (!this._destruido)
            this._mostrar(estado);
    }

    _mostrar(e) {
        const nome = e.estado === 'procurando' ? `escudo-procurando-${e.nivel ?? 1}` : `escudo-${e.estado}`;
        this._icone.gicon = Gio.FileIcon.new(Gio.File.new_for_path(`${this._pasta}/arte/${nome}.svg`));

        this.menu.removeAll();
        const titulo = new PopupMenu.PopupMenuItem(e.titulo, {reactive: false});
        titulo.add_style_class_name(`guarnicao-menu-titulo ${e.estado}`);
        this.menu.addMenuItem(titulo);
        for (const linha of e.linhas ?? []) {
            const item = new PopupMenu.PopupMenuItem(linha, {reactive: false});
            item.add_style_class_name('guarnicao-menu-linha');
            this.menu.addMenuItem(item);
        }
        if (!e.acoes?.length)
            return;
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        e.acoes.forEach((acao, i) => {
            const item = new PopupMenu.PopupMenuItem(ROTULOS_MENU[acao] ?? acao);
            // Com problema, a ação que resolve vem primeiro e dourada (barra-v2).
            if (i === 0 && e.estado !== 'certo')
                item.add_style_class_name('guarnicao-acao-principal');
            item.connect('activate', () => this._comandos.rodar(COMANDOS_MENU[acao]));
            this.menu.addMenuItem(item);
        });
    }

    destroy() {
        this._destruido = true;
        GLib.source_remove(this._relogio);
        if (this._agendado)
            GLib.source_remove(this._agendado);
        this._vigia.cancel();
        super.destroy();
    }
});
