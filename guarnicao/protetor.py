"""Proteção antes da execução: o kernel pergunta, o Guarnição responde.

Com o fanotify e FAN_OPEN_EXEC_PERM, cada execve() de um arquivo fica parado
até o Guarnição responder "pode" ou "não pode". Uma ameaça conhecida nem chega
a rodar: quem tentou recebe "Operação não permitida".

O risco de um vigia assim é travar o computador. Por isso:

- **Fail-open por prazo:** se a análise demorar mais que PRAZO, um relógio
  separado libera a execução; a análise continua e, se der ameaça, avisa.
- **Fail-open por queda:** se o processo morrer, o kernel libera sozinho tudo
  que estava esperando.
- **A thread que lê os eventos nunca executa programas** (nem notify-send):
  ela esperaria por uma execução que espera por ela mesma.
- Programas do sistema (/usr, /bin, /lib... de root, sem escrita para outros)
  passam direto: só root muda esses arquivos, e com root o jogo já acabou.
  O que importa é o que chega pela sua conta: /home, /tmp, /dev/shm, /opt...

Limite: só vale para o que é *executado*. `python script.py` executa o
python (confiável), não o script; scripts com `#!` e permissão de execução, e
binários, passam por aqui.
"""

import ctypes
import ctypes.util
import errno
import multiprocessing
import os
import queue
import select
import struct
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterator

from .scanner import Resultado

# <linux/fanotify.h>
FAN_CLOEXEC = 0x00000001
FAN_CLASS_CONTENT = 0x00000004
FAN_UNLIMITED_QUEUE = 0x00000010
FAN_MARK_ADD = 0x00000001
FAN_MARK_MOUNT = 0x00000010
FAN_MARK_FILESYSTEM = 0x00000100
FAN_OPEN_EXEC_PERM = 0x00040000
FAN_Q_OVERFLOW = 0x00004000
FAN_ALLOW, FAN_DENY = 0x01, 0x02
VERSAO_METADADOS = 3
# struct fanotify_event_metadata: event_len, vers, reserved, metadata_len, mask, fd, pid
METADADOS = struct.Struct("=IBBHQii")
RESPOSTA = struct.Struct("=iI")       # struct fanotify_response: fd, response

PRAZO = 2.0                  # segundos até liberar uma execução sem veredito
VALIDADE = 3600.0            # um veredito vale 1 h: a base de hashes muda de hora em hora
LIMITE_DO_CACHE = 20000
SISTEMAS_DE_ARQUIVOS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "jfs", "bcachefs", "zfs",
                        "tmpfs", "vfat", "exfat", "ntfs3", "overlay"}
# Sem fuse: o programa que serve um fuse pode precisar executar algo para
# responder a leitura que a nossa análise pediu, e os dois esperariam um pelo outro.
CONFIAVEIS = ("/usr/", "/bin/", "/sbin/", "/lib/", "/lib32/", "/lib64/", "/libx32/")


@dataclass
class Evento:
    mascara: int
    fd: int
    pid: int


@dataclass
class Decisao:
    caminho: Path
    pid: int
    quem: str                       # o programa que pediu a execução
    permitido: bool
    motivo: str                     # "ameaça", "suspeito", "prazo" ou "erro"
    resultado: Resultado | None = None


def ler_eventos(dados: bytes) -> Iterator[Evento]:
    """Um read() do fanotify pode trazer vários eventos colados."""
    pos = 0
    while pos + METADADOS.size <= len(dados):
        tamanho, versao, _, _, mascara, fd, pid = METADADOS.unpack_from(dados, pos)
        if versao != VERSAO_METADADOS:
            raise OSError(errno.EPROTO, f"fanotify com metadados versão {versao}, esperava {VERSAO_METADADOS}")
        if tamanho < METADADOS.size:
            break
        yield Evento(mascara, fd, pid)
        pos += tamanho


def _desescapar(texto: str) -> str:
    # /proc/self/mounts troca espaço por \040, tab por \011 etc.
    return texto.encode().decode("unicode_escape").encode("latin-1").decode(errors="replace")


def pontos_de_montagem(mounts: Path = Path("/proc/self/mounts")) -> list[Path]:
    """Um ponto por sistema de arquivos de verdade (discos, tmpfs), sem repetir dispositivo."""
    vistos, pontos = set(), []
    for linha in mounts.read_text().splitlines():
        _, ponto, tipo, *_ = linha.split()
        if tipo not in SISTEMAS_DE_ARQUIVOS:
            continue
        ponto = Path(_desescapar(ponto))
        try:
            dev = os.stat(ponto).st_dev
        except OSError:
            continue
        if dev not in vistos:
            vistos.add(dev)
            pontos.append(ponto)
    return pontos


def confiavel(caminho: str, st: os.stat_result) -> bool:
    if caminho.startswith("/usr/local/"):
        return False
    return caminho.startswith(CONFIAVEIS) and st.st_uid == 0 and not st.st_mode & 0o022


def _quem(pid: int) -> str:
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return f"pid {pid}"


class _Pendente:
    """Uma execução esperando resposta. Responde uma vez só, venha de quem vier."""

    def __init__(self, evento: Evento, caminho: str, st: os.stat_result, prazo: float):
        self.evento, self.caminho, self.st = evento, caminho, st
        self.vence = time.monotonic() + prazo
        self.quem = _quem(evento.pid)
        self.chave = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        self.caronas: list["_Pendente"] = []    # execuções do mesmo arquivo durante a análise
        self.veredito = True                    # o que a análise decidiu (o prazo pode ter respondido antes)
        self._trava = threading.Lock()
        self.respondido: bool | None = None     # None: ainda não; senão, se permitiu

    def responder(self, enviar: Callable[[int, bool], None], permitir: bool) -> bool:
        with self._trava:
            if self.respondido is not None:
                return False
            self.respondido = permitir
        enviar(self.evento.fd, permitir)
        return True


class _NaoSei:
    pass


NAO_SEI = _NaoSei()
Analisador = Callable[[Path], Resultado]


class Protetor:
    """Decide cada execução. `fabrica()` é chamada uma vez por trabalhador e
    devolve a função de análise dele (o YARA-X não divide o scanner entre threads).

    `ao_decidir` recebe só o que merece aviso: bloqueios, suspeitos e ameaças
    liberadas pelo prazo. Ele roda numa thread própria, então pode notificar.
    """

    def __init__(self, fabrica: Callable[[], Analisador], ao_decidir: Callable[[Decisao], None],
                 bloquear: bool = True, prazo: float = PRAZO, trabalhadores: int = 3,
                 enviar: Callable[[int, bool], None] | None = None):
        self.fabrica, self.ao_decidir = fabrica, ao_decidir
        self.bloquear, self.prazo = bloquear, prazo
        self.fan: int | None = None
        self._enviar = enviar or self._enviar_ao_kernel
        self._fila: queue.Queue[_Pendente | None] = queue.Queue()
        self._avisos: queue.Queue[Decisao | None] = queue.Queue()
        self._pendentes: set[_Pendente] = set()
        self._em_analise: dict[tuple, _Pendente] = {}
        self._trava = threading.Lock()
        self._trava_fan = threading.Lock()
        self._cache: dict[tuple[int, int], tuple[tuple, float, Decisao | None]] = {}
        self._parar = threading.Event()
        self._threads = [threading.Thread(target=self._trabalhar, name=f"guarnicao-analise-{i}", daemon=True)
                         for i in range(trabalhadores)]
        self._threads += [threading.Thread(target=self._relogio, name="guarnicao-prazo", daemon=True),
                          threading.Thread(target=self._avisar, name="guarnicao-avisos", daemon=True)]
        self.estatisticas = {"eventos": 0, "confiaveis": 0, "cache": 0, "analisados": 0, "prazo": 0, "bloqueados": 0}

    # --- kernel -------------------------------------------------------------

    def abrir(self, pontos: list[Path] | None = None) -> list[Path]:
        """Pede ao kernel os eventos de execução. Precisa de root (CAP_SYS_ADMIN)."""
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
        libc.fanotify_mark.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_uint64, ctypes.c_int, ctypes.c_char_p]
        fan = libc.fanotify_init(FAN_CLASS_CONTENT | FAN_CLOEXEC | FAN_UNLIMITED_QUEUE,
                                 os.O_RDONLY | os.O_LARGEFILE | os.O_CLOEXEC)
        if fan < 0:
            erro = ctypes.get_errno()
            raise OSError(erro, f"fanotify_init: {os.strerror(erro)}")
        marcados = []
        for ponto in pontos if pontos is not None else pontos_de_montagem():
            alvo = os.fsencode(ponto)
            # O sistema de arquivos inteiro pega também as montagens "bind" dele.
            if libc.fanotify_mark(fan, FAN_MARK_ADD | FAN_MARK_FILESYSTEM, FAN_OPEN_EXEC_PERM, -100, alvo) == 0 or \
                    libc.fanotify_mark(fan, FAN_MARK_ADD | FAN_MARK_MOUNT, FAN_OPEN_EXEC_PERM, -100, alvo) == 0:
                marcados.append(ponto)
        if not marcados:
            os.close(fan)
            raise OSError(errno.ENODEV, "nenhum sistema de arquivos aceitou a marca do fanotify")
        self.fan = fan
        return marcados

    def _enviar_ao_kernel(self, fd: int, permitir: bool) -> None:
        # Com a trava: depois do parar(), o número do descritor pode ser
        # reaproveitado por outro arquivo, e a resposta iria parar nele.
        with self._trava_fan:
            if self.fan is None:
                return
            try:
                os.write(self.fan, RESPOSTA.pack(fd, FAN_ALLOW if permitir else FAN_DENY))
            except OSError:
                pass    # o processo que esperava já morreu

    def rodar(self) -> None:
        """Lê eventos até `parar()`. Fica na thread de quem chamou."""
        fan = self.fan
        if fan is None:
            raise RuntimeError("chame abrir() antes de rodar()")
        self.iniciar()
        try:
            while not self._parar.is_set():
                prontos, _, _ = select.select([fan], [], [], 0.5)
                if not prontos:
                    continue
                try:
                    dados = os.read(fan, METADADOS.size * 512)
                except (InterruptedError, BlockingIOError):
                    continue
                for evento in ler_eventos(dados):
                    self.tratar(evento)
        finally:
            self.parar()

    def iniciar(self) -> None:
        for t in self._threads:
            t.start()

    def parar(self) -> None:
        if self._parar.is_set():
            return
        self._parar.set()
        for _ in self._threads:
            self._fila.put(None)
        self._avisos.put(None)
        with self._trava_fan:
            if self.fan is not None:
                os.close(self.fan)       # o kernel libera tudo que ainda esperava
                self.fan = None

    # --- decisão ------------------------------------------------------------

    def tratar(self, evento: Evento) -> None:
        """Roda na thread que lê o kernel: rápido, sem executar nada, sem esperar análise."""
        if evento.mascara & FAN_Q_OVERFLOW or evento.fd < 0:
            return
        self.estatisticas["eventos"] += 1
        try:
            st = os.fstat(evento.fd)
            caminho = os.readlink(f"/proc/self/fd/{evento.fd}")
        except OSError:
            return self._liberar(evento)
        if evento.pid == os.getpid() or confiavel(caminho, st):
            self.estatisticas["confiaveis"] += 1
            return self._liberar(evento)
        if (guardado := self._do_cache(st)) is not NAO_SEI:
            assert not isinstance(guardado, _NaoSei)
            self.estatisticas["cache"] += 1
            permitir = guardado is None or not self.bloquear or guardado.motivo != "ameaça"
            self._enviar(evento.fd, permitir)
            os.close(evento.fd)
            if guardado is not None:
                self._avisos.put(Decisao(Path(caminho), evento.pid, _quem(evento.pid), permitir,
                                         guardado.motivo, guardado.resultado))
            return
        pendente = _Pendente(evento, caminho, st, self.prazo)
        with self._trava:
            principal = self._em_analise.get(pendente.chave)
            if principal is None:
                self._em_analise[pendente.chave] = pendente
            else:
                # Mesmo arquivo já em análise (um programa que se executa de novo
                # ao abrir): pega carona, com o mesmo prazo. Esperar outro prazo
                # inteiro não traria veredito nenhum a mais.
                pendente.vence = principal.vence
                principal.caronas.append(pendente)
            self._pendentes.add(pendente)
        if principal is None:
            self._fila.put(pendente)

    def _liberar(self, evento: Evento) -> None:
        self._enviar(evento.fd, True)
        os.close(evento.fd)

    @staticmethod
    def _identidade(st: os.stat_result) -> tuple:
        return st.st_size, st.st_mtime_ns, st.st_ctime_ns

    def _do_cache(self, st: os.stat_result) -> "Decisao | None | _NaoSei":
        """A decisão guardada (None = limpo), ou NAO_SEI se não há ou venceu."""
        entrada = self._cache.get((st.st_dev, st.st_ino))
        if entrada and entrada[0] == self._identidade(st) and time.monotonic() - entrada[1] < VALIDADE:
            return entrada[2]
        return NAO_SEI

    def _guardar(self, st: os.stat_result, decisao: Decisao | None) -> None:
        if len(self._cache) >= LIMITE_DO_CACHE:
            self._cache.clear()
        self._cache[(st.st_dev, st.st_ino)] = (self._identidade(st), time.monotonic(), decisao)

    def _trabalhar(self) -> None:
        analisar = self.fabrica()
        while (p := self._fila.get()) is not None:
            try:
                self._julgar(p, analisar)
            finally:
                with self._trava:
                    self._em_analise.pop(p.chave, None)
                    caronas, p.caronas = p.caronas, []
                    self._pendentes.difference_update([p, *caronas])
                for carona in caronas:
                    if carona.responder(self._enviar, p.veredito) and not p.veredito:
                        self.estatisticas["bloqueados"] += 1
                    os.close(carona.evento.fd)
                os.close(p.evento.fd)

    def _julgar(self, p: _Pendente, analisar: Analisador) -> None:
        # Analisa pelo caminho (as heurísticas olham nome e extensão) se ele
        # ainda é o mesmo arquivo; senão, pelo descritor que o kernel deu.
        # /proc/<pid>, não /proc/self: quem analisa é outro processo.
        alvo, pelo_fd = Path(p.caminho), Path(f"/proc/{os.getpid()}/fd/{p.evento.fd}")
        try:
            st = os.stat(alvo)
            if (st.st_dev, st.st_ino) != (p.st.st_dev, p.st.st_ino):
                alvo = pelo_fd
        except OSError:
            alvo = pelo_fd
        try:
            try:
                resultado = analisar(alvo)
            except OSError:
                if alvo == pelo_fd:
                    raise
                # Apagado ou trocado no meio da análise (malware que se apaga
                # depois de executar): o descritor do kernel ainda é o arquivo.
                resultado = analisar(pelo_fd)
            resultado.caminho = Path(p.caminho)
        except Exception as erro:
            p.responder(self._enviar, True)
            self._avisos.put(Decisao(Path(p.caminho), p.evento.pid, p.quem, True, "erro", None))
            print(f"[erro] {p.caminho}: {erro}", flush=True)
            return
        self.estatisticas["analisados"] += 1
        if resultado.infectado:
            decisao = Decisao(Path(p.caminho), p.evento.pid, p.quem, not self.bloquear, "ameaça", resultado)
        elif resultado.suspeito:
            decisao = Decisao(Path(p.caminho), p.evento.pid, p.quem, True, "suspeito", resultado)
        else:
            decisao = None
        self._guardar(p.st, decisao)
        permitir = p.veredito = decisao is None or decisao.permitido
        if p.responder(self._enviar, permitir):
            if not permitir:
                self.estatisticas["bloqueados"] += 1
        elif decisao is not None and decisao.motivo == "ameaça":
            # Já tinha sido liberado pelo prazo: avisa que rodou. Cópia, porque o
            # cache segue dizendo "ameaça" e a próxima execução é bloqueada.
            decisao = replace(decisao, permitido=True, motivo="prazo")
        if decisao is not None:
            self._avisos.put(decisao)

    def _relogio(self) -> None:
        """Libera quem passou do prazo. Nunca espera nada além do próprio sono."""
        while not self._parar.wait(0.05):
            agora = time.monotonic()
            with self._trava:
                vencidos = [p for p in self._pendentes if p.vence <= agora]
            for p in vencidos:
                try:
                    if p.responder(self._enviar, True):
                        self.estatisticas["prazo"] += 1
                except Exception:
                    pass

    def _avisar(self) -> None:
        while (decisao := self._avisos.get()) is not None:
            try:
                self.ao_decidir(decisao)
            except Exception as erro:
                print(f"[erro ao avisar] {erro}", flush=True)


# --- análise em processos separados -----------------------------------------
#
# O YARA-X segura o GIL enquanto analisa: 3,5 s num binário de 300 MB em que
# nenhuma outra thread do processo roda, nem o relógio do prazo. Analisando em
# outros processos, o que lê o kernel e o relógio nunca esperam pelo GIL.

_estado: dict = {}
RECONFERIR = 60.0


def _iniciar_processo() -> None:
    import signal

    from . import assinaturas, clamav, regras_yara
    # Ctrl+C no terminal chega ao grupo inteiro; quem encerra os analisadores é o principal.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _estado.update(banco=assinaturas.carregar(), yara=regras_yara.carregar(), clamav=clamav.conectar(),
                   regras=regras_yara.regras_das_bases(), conferido=time.monotonic())


def _analisar_no_processo(caminho: str) -> Resultado:
    from . import clamav, regras_yara, scanner
    e = _estado
    # O serviço fica dias no ar: regras novas do timer, e o clamd que reiniciou.
    if time.monotonic() - e["conferido"] > RECONFERIR:
        e["conferido"] = time.monotonic()
        if (regras := regras_yara.regras_das_bases()) != e["regras"]:
            e["yara"], e["regras"] = regras_yara.carregar(), regras
        if e["clamav"] is None:
            e["clamav"] = clamav.conectar()
    return scanner.analisar(Path(caminho), e["banco"], e["yara"], e["clamav"])


class Analisadores:
    """Um grupo de processos que analisam; `analisar` serve de Analisador para o Protetor."""

    def __init__(self, processos: int = 2, limite: float = 120.0):
        # Cada processo tem as regras compiladas (uns 170 MB com o YARA Forge).
        self.limite = limite
        self.grupo = ProcessPoolExecutor(processos, mp_context=multiprocessing.get_context("forkserver"),
                                         initializer=_iniciar_processo)
        # Sobe os processos e compila as regras já, antes de o kernel começar a perguntar.
        for f in [self.grupo.submit(time.sleep, 0.5) for _ in range(processos)]:
            f.result()

    def analisar(self, caminho: Path) -> Resultado:
        return self.grupo.submit(_analisar_no_processo, str(caminho)).result(timeout=self.limite)

    def fechar(self) -> None:
        self.grupo.shutdown(wait=False, cancel_futures=True)
