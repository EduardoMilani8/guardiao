"""Monitor de comportamento: o que um processo está fazendo, não o que ele é.

Assinaturas e regras olham o arquivo, e malware novo muda o arquivo o tempo
todo. O comportamento muda bem menos: um shell reverso continua sendo um
shell falando com a rede, e um minerador continua queimando CPU conectado a
um pool. Aqui tudo vem do /proc, sem root (sem ele, só os seus processos).
"""

import ipaddress
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

PROC = Path("/proc")
SHELLS = {"sh", "bash", "dash", "zsh", "ksh", "mksh", "fish", "ash", "busybox", "tcsh", "csh"}
INTERPRETADORES = {"python", "python3", "perl", "ruby", "php", "node", "lua", "awk", "gawk"}
REDE = {"nc", "ncat", "netcat", "nc.traditional", "nc.openbsd", "socat", "telnet"}
PORTAS_DE_POOL = {3333, 4444, 5555, 6666, 7777, 9999, 14433, 14444, 45560, 45700}
CPU_DE_MINERADOR = 0.5        # fração de um núcleo, sustentada entre duas fotografias
ESTABELECIDA = "01"
TICKS = os.sysconf("SC_CLK_TCK")


@dataclass
class Conexao:
    protocolo: str        # "tcp", "tcp6", "udp", "udp6"
    remoto: tuple[str, int]
    estado: str

    @property
    def local(self) -> bool:
        try:
            return ipaddress.ip_address(self.remoto[0]).is_loopback
        except ValueError:
            return False

    def __str__(self) -> str:
        ip, porta = self.remoto
        return f"[{ip}]:{porta}" if ":" in ip else f"{ip}:{porta}"


@dataclass
class Processo:
    pid: int
    ppid: int
    nome: str
    exe: str
    inicio: int                                   # starttime: separa um pid reaproveitado
    cpu: int                                      # utime + stime, em ticks
    entrada_saida: dict[int, Conexao] = field(default_factory=dict)   # fd 0, 1, 2 em rede
    conexoes: list[Conexao] = field(default_factory=list)

    @property
    def programa(self) -> str:
        # python3.14 → python, socat1 (o do Ubuntu 26.04) → socat: a versão não importa aqui.
        return os.path.basename(self.exe.removesuffix(" (deleted)")).rstrip("0123456789.")


@dataclass
class Alerta:
    tipo: str             # "shell reverso" ou "minerador"
    gravidade: str        # "alta" ou "media"
    processo: Processo
    mensagem: str

    @property
    def chave(self) -> tuple:
        return self.tipo, self.processo.pid, self.processo.inicio


# --- leitura do /proc -------------------------------------------------------

def _endereco(hexa: str) -> tuple[str, int]:
    """'0100007F:0016' → ('127.0.0.1', 22). O kernel grava em ordem de máquina (little-endian)."""
    ip, porta = hexa.split(":")
    bruto = bytes.fromhex(ip)
    if len(bruto) == 4:
        endereco = ipaddress.IPv4Address(bruto[::-1])
    else:
        endereco = ipaddress.IPv6Address(b"".join(bruto[i:i + 4][::-1] for i in range(0, 16, 4)))
        endereco = endereco.ipv4_mapped or endereco
    return str(endereco), int(porta, 16)


def sockets(proc: Path = PROC) -> dict[str, Conexao]:
    """inode → conexão, de todas as tabelas de rede do kernel."""
    tabela = {}
    for protocolo in ("tcp", "tcp6", "udp", "udp6"):
        try:
            linhas = (proc / "net" / protocolo).read_text().splitlines()[1:]
        except OSError:
            continue
        for linha in linhas:
            c = linha.split()
            if len(c) > 9:
                tabela[c[9]] = Conexao(protocolo, _endereco(c[2]), c[3])
    return tabela


def _ler_processo(pasta: Path, rede: dict[str, Conexao]) -> Processo | None:
    try:
        stat = (pasta / "stat").read_text()
        exe = os.readlink(pasta / "exe")
    except OSError:
        return None   # outro usuário (sem root), thread do kernel ou já terminou
    # O nome vem entre parênteses e pode ter espaços: o resto começa depois do último ")".
    nome = stat[stat.index("(") + 1:stat.rindex(")")]
    campos = stat[stat.rindex(")") + 2:].split()
    processo = Processo(int(pasta.name), int(campos[1]), nome, exe, int(campos[19]),
                        int(campos[11]) + int(campos[12]))
    try:
        descritores = os.listdir(pasta / "fd")
    except OSError:
        return processo
    for fd in descritores:
        try:
            alvo = os.readlink(pasta / "fd" / fd)
        except OSError:
            continue
        if alvo.startswith("socket:[") and (conexao := rede.get(alvo[8:-1])):
            processo.conexoes.append(conexao)
            if fd in ("0", "1", "2"):
                processo.entrada_saida[int(fd)] = conexao
    return processo


def fotografar(proc: Path = PROC) -> dict[int, Processo]:
    rede = sockets(proc)
    fotos = {}
    for pasta in proc.iterdir():
        if pasta.name.isdigit() and (p := _ler_processo(pasta, rede)):
            fotos[p.pid] = p
    return fotos


# --- o que denuncia ---------------------------------------------------------

def shells_reversos(fotos: dict[int, Processo]) -> Iterator[Alerta]:
    for p in fotos.values():
        conexao = next((c for c in p.entrada_saida.values() if c.protocolo.startswith("tcp")), None)
        if conexao and p.programa in SHELLS | INTERPRETADORES | REDE:
            como = f"{p.programa} com a entrada e a saída ligadas a {conexao}"
        elif p.programa in SHELLS and (pai := fotos.get(p.ppid)) and pai.programa in REDE and \
                (conexao := next((c for c in pai.conexoes if c.estado == ESTABELECIDA), None)):
            # socat exec:bash,pty: o shell ganha um terminal falso, e quem segura a conexão é o pai.
            como = f"{p.programa} aberto pelo {pai.programa} ({pai.pid}), conectado a {conexao}"
        else:
            continue
        gravidade = "media" if conexao.local else "alta"
        quem = "alguém nesta máquina" if conexao.local else "quem está do outro lado"
        yield Alerta("shell reverso", gravidade, p,
                     f"{como}: {quem} pode digitar comandos como você (pid {p.pid}; para encerrar: kill {p.pid})")


def mineradores(antes: dict[int, Processo], depois: dict[int, Processo], segundos: float) -> Iterator[Alerta]:
    for p in depois.values():
        anterior = antes.get(p.pid)
        if anterior is None or anterior.inicio != p.inicio or segundos <= 0:
            continue
        uso = (p.cpu - anterior.cpu) / TICKS / segundos
        pool = next((c for c in p.conexoes if c.protocolo.startswith("tcp") and c.estado == ESTABELECIDA
                     and c.remoto[1] in PORTAS_DE_POOL), None)
        if uso >= CPU_DE_MINERADOR and pool:
            yield Alerta("minerador", "alta", p,
                         f"{p.nome} usa {uso:.0%} de um núcleo conectado a {pool}, porta típica de pool "
                         f"de mineração (pid {p.pid}; para encerrar: kill {p.pid})")


def examinar(intervalo: float = 3.0, proc: Path = PROC) -> list[Alerta]:
    """Uma olhada: duas fotografias, para medir a CPU entre elas."""
    antes = fotografar(proc)
    time.sleep(intervalo)
    depois = fotografar(proc)
    return [*shells_reversos(depois), *mineradores(antes, depois, intervalo)]


class Vigia:
    """Olha de tempos em tempos e avisa uma vez por processo."""

    def __init__(self, ao_alertar: Callable[[Alerta], None], intervalo: float = 5.0, proc: Path = PROC):
        self.ao_alertar, self.intervalo, self.proc = ao_alertar, intervalo, proc
        self._avisados: set[tuple] = set()
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._rodar, name="guarnicao-comportamento", daemon=True)

    def _rodar(self) -> None:
        antes, quando = fotografar(self.proc), time.monotonic()
        while not self._parar.wait(self.intervalo):
            depois, agora = fotografar(self.proc), time.monotonic()
            for alerta in [*shells_reversos(depois), *mineradores(antes, depois, agora - quando)]:
                if alerta.chave not in self._avisados:
                    self._avisados.add(alerta.chave)
                    self.ao_alertar(alerta)
            vivos = {(p.pid, p.inicio) for p in depois.values()}
            self._avisados = {c for c in self._avisados if c[1:] in vivos}
            antes, quando = depois, agora

    def __enter__(self) -> "Vigia":
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._parar.set()
        self._thread.join(timeout=self.intervalo + 1)
