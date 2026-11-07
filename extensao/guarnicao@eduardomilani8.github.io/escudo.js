import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

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

    async atualizar() {
        if (this._ocupado)
            return;
        this._ocupado = true;
        try {
            this._mostrar(await this._comandos.json(['estado', '--json']));
        } catch (e) {
            logError(e, 'Guarnição: não deu para ler o estado');
        } finally {
            this._ocupado = false;
        }
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
        GLib.source_remove(this._relogio);
        this._vigia.cancel();
        super.destroy();
    }
});
