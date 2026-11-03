"""Caçador de persistência e rootkits.

A varredura procura arquivos ruins. Aqui a pergunta é outra: alguma coisa já
se instalou e está se escondendo? Malware em Linux costuma fazer três coisas:
injetar uma biblioteca em todo programa (ld.so.preload, LD_PRELOAD), rodar de
pastas temporárias ou apagar o próprio executável depois de iniciar, e se
cadastrar para voltar depois do reboot (systemd, cron, autostart).

O critério central é "isto veio de um pacote?". O que o apt instalou está
registrado em /var/lib/dpkg/info; o resto é listado e entregue ao scanner,
que já sabe julgar conteúdo (hash, ClamAV, YARA, heurísticas).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from . import scanner

PRELOAD = Path("/etc/ld.so.preload")
PROC = Path("/proc")
DPKG_INFO = Path("/var/lib/dpkg/info")
PASTAS_TEMPORARIAS = ("/tmp/", "/var/tmp/", "/dev/shm/")
FUNDIDAS = ("bin", "sbin", "lib", "lib32", "lib64", "libx32")   # usrmerge: /lib → /usr/lib
ORDEM = {"alta": 0, "media": 1, "info": 2}

Julgar = Callable[[Path], "scanner.Resultado | None"]


@dataclass
class Achado:
    gravidade: str        # "alta", "media" ou "info"
    categoria: str        # ex.: "ld.so.preload", "processo", "systemd"
    arquivo: Path
    mensagem: str


class Pacotes:
    """Quais arquivos vieram de um pacote .deb."""

    def __init__(self, pasta: Path = DPKG_INFO):
        self.arquivos: set[str] = set()
        for lista in pasta.glob("*.list"):
            try:
                self.arquivos.update(lista.read_text(errors="replace").splitlines())
            except OSError:
                continue

    def dono(self, caminho: Path | str) -> bool:
        return any(c in self.arquivos for c in _variantes(str(caminho)))


def _variantes(caminho: str) -> set[str]:
    # O pacote pode ter registrado /lib/x ou /usr/lib/x, e o arquivo pode ser um link.
    nomes = {caminho, os.path.realpath(caminho)}
    for nome in list(nomes):
        partes = nome.split("/")
        if len(partes) > 2 and partes[1] == "usr" and partes[2] in FUNDIDAS:
            nomes.add("/" + "/".join(partes[2:]))
        elif len(partes) > 1 and partes[1] in FUNDIDAS:
            nomes.add("/usr" + nome)
    return nomes


def em_pasta_temporaria(caminho: str) -> bool:
    return caminho.startswith(PASTAS_TEMPORARIAS)


def juiz(banco, yara=None, clamav=None) -> Julgar:
    """O scanner de sempre, para julgar o conteúdo do que o caçador encontrar."""
    def julgar(caminho: Path) -> scanner.Resultado | None:
        # /proc/<pid>/exe é um link "mágico" para o executável, mesmo apagado do
        # disco. O ClamAV abre com O_NOFOLLOW e não passaria dele.
        cl = None if str(caminho).startswith("/proc/") else clamav
        try:
            return scanner.analisar(caminho, banco, yara, cl)
        except OSError:
            return None
    return julgar


def nao_julgar(_caminho: Path) -> None:
    return None


def cacar(julgar: Julgar = nao_julgar, pacotes: Pacotes | None = None) -> list[Achado]:
    pacotes = pacotes or Pacotes()
    achados = [
        *preload(pacotes),
        *ld_preload_em_processos(pacotes),
        *processos(julgar, pacotes),
    ]
    return sorted(achados, key=lambda a: (ORDEM.get(a.gravidade, 9), a.categoria, str(a.arquivo)))


# --- bibliotecas injetadas --------------------------------------------------

def _gravidade_da_biblioteca(lib: str, pacotes: Pacotes) -> tuple[str, str]:
    if em_pasta_temporaria(lib):
        return "alta", "fica numa pasta temporária"
    if not os.path.exists(lib):
        return "media", "o arquivo nem existe mais"
    if pacotes.dono(lib):
        return "info", "veio de um pacote"
    return "alta", "não veio de nenhum pacote"


def preload(pacotes: Pacotes, arquivo: Path = PRELOAD) -> Iterator[Achado]:
    """O /etc/ld.so.preload carrega bibliotecas em TODO programa do sistema.

    Quase nenhum sistema usa: é o esconderijo clássico de rootkits de
    usuário (Jynx, Azazel, Symbiote), que dali escondem arquivos e processos.
    """
    try:
        texto = arquivo.read_text(errors="replace")
    except FileNotFoundError:
        return
    except OSError as erro:
        yield Achado("media", "ld.so.preload", arquivo, f"existe mas não deu para ler: {erro.strerror}")
        return
    libs = [lib for linha in texto.splitlines() if not linha.lstrip().startswith("#")
            for lib in linha.replace(":", " ").split()]
    if not libs:
        yield Achado("info", "ld.so.preload", arquivo, "existe, mas está vazio")
    for lib in libs:
        gravidade, motivo = _gravidade_da_biblioteca(lib, pacotes)
        yield Achado(gravidade, "ld.so.preload", Path(lib),
                     f"injetada em todo programa do sistema; {motivo}")


def _ler_ambiente(pid: Path) -> dict[str, str]:
    try:
        bruto = (pid / "environ").read_bytes()
    except OSError:
        return {}   # processo de outro usuário (sem root) ou que já terminou
    variaveis = {}
    for item in bruto.split(b"\0"):
        nome, igual, valor = item.partition(b"=")
        if igual:
            variaveis[nome.decode(errors="replace")] = valor.decode(errors="replace")
    return variaveis


def nome_do_processo(pid: Path) -> str:
    try:
        return (pid / "comm").read_text().strip()
    except OSError:
        return "?"


def ld_preload_em_processos(pacotes: Pacotes, proc: Path = PROC) -> Iterator[Achado]:
    """LD_PRELOAD faz o mesmo que o ld.so.preload, só para um processo e seus filhos."""
    por_lib: dict[str, list[str]] = {}
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        valor = _ler_ambiente(pid).get("LD_PRELOAD", "")
        for lib in valor.replace(":", " ").split():
            # Snaps carregam bibliotecas do próprio pacote, com $LIB que o ld.so expande.
            if lib.startswith("/snap/"):
                continue
            por_lib.setdefault(lib, []).append(f"{nome_do_processo(pid)} ({pid.name})")
    for lib, processos in por_lib.items():
        gravidade, motivo = _gravidade_da_biblioteca(lib, pacotes)
        quem = ", ".join(processos[:5]) + (f" e mais {len(processos) - 5}" if len(processos) > 5 else "")
        yield Achado(gravidade, "LD_PRELOAD", Path(lib), f"injetada em {quem}; {motivo}")


# --- processos --------------------------------------------------------------

def _avaliar_executavel(exe: str, pacotes: Pacotes) -> tuple[str, str] | None:
    caminho = exe.removesuffix(" (deleted)")
    if caminho.startswith("/memfd:"):
        if "runc" in caminho:
            return None   # o Docker roda o runc assim de propósito
        return "alta", "roda direto da memória (memfd), sem nenhum arquivo no disco"
    if em_pasta_temporaria(caminho):
        return "alta", "roda de uma pasta temporária"
    if exe.endswith(" (deleted)"):
        if os.path.exists(caminho) or pacotes.dono(caminho):
            return "info", "foi atualizado depois de abrir; reinicie-o para usar a versão nova"
        return "media", "o executável foi apagado depois de iniciar, truque comum de malware"
    return None


def processos(julgar: Julgar, pacotes: Pacotes, proc: Path = PROC) -> Iterator[Achado]:
    """Processos rodando de /tmp, da memória ou de um executável apagado."""
    grupos: dict[tuple[str, str, str], list[Path]] = {}
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            exe = os.readlink(pid / "exe")
        except OSError:
            continue   # thread do kernel, outro usuário (sem root) ou já terminou
        if avaliacao := _avaliar_executavel(exe, pacotes):
            grupos.setdefault((exe.removesuffix(" (deleted)"), *avaliacao), []).append(pid)

    for (exe, gravidade, motivo), pids in grupos.items():
        quem = ", ".join(f"{nome_do_processo(p)} ({p.name})" for p in pids[:5])
        if len(pids) > 5:
            quem += f" e mais {len(pids) - 5}"
        mensagem = f"{motivo}: {quem}"
        # O executável continua legível por /proc/<pid>/exe, mesmo apagado do disco.
        resultado = julgar(pids[0] / "exe") if gravidade != "info" else None
        if resultado and resultado.infectado:
            gravidade, mensagem = "alta", f"{resultado.ameaca} · {mensagem}"
        elif resultado and resultado.suspeito:
            mensagem += "".join(f"\n           - {m}" for m in resultado.motivos)
        yield Achado(gravidade, "processo", Path(exe), mensagem)
