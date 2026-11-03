"""Monitor em tempo real: analisa arquivos assim que chegam numa pasta."""

import queue
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import clamav, regras_yara, scanner

# Downloads em andamento: o navegador renomeia para o nome final ao terminar.
EXT_TEMPORARIAS = {".part", ".crdownload", ".download", ".partial", ".tmp"}
JANELA_REPETICAO = 2.0            # segundos em que eventos repetidos do mesmo arquivo são ignorados
RECONECTAR_CLAMAV = 300           # segundos entre tentativas de achar o clamd


class _Coletor(FileSystemEventHandler):
    """Transforma eventos do inotify em caminhos prontos para análise."""

    def __init__(self, fila: queue.Queue):
        self.fila = fila

    def on_closed(self, event):   # arquivo terminou de ser escrito
        if not event.is_directory:
            self.fila.put(Path(event.src_path))

    def on_moved(self, event):    # ".part" virou nome final, ou arquivo movido para cá
        if event.is_directory:
            self._recuperar(Path(event.dest_path))
        else:
            self.fila.put(Path(event.dest_path))

    def on_created(self, event):
        if event.is_directory:
            self._recuperar(Path(event.src_path))

    def _recuperar(self, pasta: Path) -> None:
        # O inotify só passa a vigiar uma pasta nova instantes depois de ela ser
        # criada; arquivos gravados nesse intervalo (ex.: extrair um zip) não
        # geram evento, então varremos o que já existe dentro dela.
        for arquivo in pasta.rglob("*"):
            if arquivo.is_file():
                self.fila.put(arquivo)


class Monitor:
    """Vigia pastas e chama `ao_analisar(resultado)` para cada arquivo novo.

    Não decide o que fazer com o resultado: quem usa (CLI, futuro launcher)
    escolhe se imprime, notifica ou isola.
    """

    def __init__(
        self,
        pastas: list[Path],
        banco: scanner.BancoDeHashes,
        ao_analisar: Callable[[scanner.Resultado], None],
        ao_erro: Callable[[Path, Exception], None] | None = None,
        usar_yara: bool = True,
    ):
        self.pastas = pastas
        self.banco = banco
        self.ao_analisar = ao_analisar
        self.ao_erro = ao_erro
        self.usar_yara = usar_yara
        self._fila: queue.Queue[Path | None] = queue.Queue()
        self._observador = Observer()
        self._trabalhador = threading.Thread(target=self._trabalhar, daemon=True)

    def iniciar(self) -> None:
        coletor = _Coletor(self._fila)
        for pasta in self.pastas:
            self._observador.schedule(coletor, str(pasta), recursive=True)
        self._observador.start()
        self._trabalhador.start()

    def parar(self) -> None:
        self._observador.stop()
        self._observador.join()
        self._fila.put(None)          # sinaliza fim para o trabalhador
        self._trabalhador.join()

    def __enter__(self):
        self.iniciar()
        return self

    def __exit__(self, *_):
        self.parar()

    def _trabalhar(self) -> None:
        # O Scanner do YARA-X só pode ser usado na thread que o criou.
        yara = regras_yara.carregar() if self.usar_yara else None
        regras_em_uso = regras_yara.regras_das_bases()
        cliente, tentou_clamav = clamav.conectar(), time.monotonic()
        vistos: dict[Path, float] = {}
        while (caminho := self._fila.get()) is not None:
            if caminho.suffix.lower() in EXT_TEMPORARIAS:
                continue
            if not caminho.is_file() or caminho.is_symlink():
                continue

            # Um mesmo download pode gerar "fechado" e "movido" quase juntos.
            agora = time.monotonic()
            if agora - vistos.get(caminho, -JANELA_REPETICAO) < JANELA_REPETICAO:
                continue
            vistos[caminho] = agora

            # O monitor fica dias aberto: se o timer trouxe regras novas (o link
            # `atual` de uma base mudou), recompila antes de analisar.
            if self.usar_yara and regras_yara.regras_das_bases() != regras_em_uso:
                yara, regras_em_uso = regras_yara.carregar(), regras_yara.regras_das_bases()
            # O clamd pode ter sido instalado ou reiniciado depois do monitor abrir.
            if cliente is None and agora - tentou_clamav > RECONECTAR_CLAMAV:
                cliente, tentou_clamav = clamav.conectar(), agora

            # Qualquer erro fica restrito a este arquivo: se a thread morresse,
            # o monitor pareceria ativo sem analisar mais nada.
            try:
                self.ao_analisar(scanner.analisar(caminho, self.banco, yara, cliente))
            except Exception as erro:
                if self.ao_erro:
                    self.ao_erro(caminho, erro)
