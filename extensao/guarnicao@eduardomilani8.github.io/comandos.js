import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

Gio._promisify(Gio.Subprocess.prototype, 'communicate_utf8_async');

// Roda "python -m guarnicao ..." a partir da pasta do projeto. O instalador grava
// config.json ao lado da extensão dizendo onde ela está.
export class Comandos {
    constructor(pastaDaExtensao) {
        const [, bytes] = GLib.file_get_contents(GLib.build_filenamev([pastaDaExtensao, 'config.json']));
        const config = JSON.parse(new TextDecoder().decode(bytes));
        this._python = config.python;
        this._pasta = config.pasta;
    }

    // Lista de argumentos, nunca shell: um nome de arquivo malicioso continua texto.
    _iniciar(args, flags) {
        const lancador = new Gio.SubprocessLauncher({flags});
        lancador.set_cwd(this._pasta);
        return lancador.spawnv([this._python, '-m', 'guarnicao', ...args]);
    }

    rodar(args) {
        try {
            this._iniciar(args, Gio.SubprocessFlags.NONE);
        } catch (e) {
            logError(e, 'Guarnição: não deu para rodar o comando');
        }
    }

    async json(args) {
        const processo = this._iniciar(args, Gio.SubprocessFlags.STDOUT_PIPE);
        const [saida] = await processo.communicate_utf8_async(null, null);
        return JSON.parse(saida);
    }
}
