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

import base64
import hashlib
import os
import pwd
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from . import regras_yara, scanner
from .caminhos import casa_real

PRELOAD = Path("/etc/ld.so.preload")
PROC = Path("/proc")
DPKG_INFO = Path("/var/lib/dpkg/info")
PASTAS_TEMPORARIAS = ("/tmp/", "/var/tmp/", "/dev/shm/")
FUNDIDAS = ("bin", "sbin", "lib", "lib32", "lib64", "libx32")   # usrmerge: /lib → /usr/lib
EXECUTAVEIS = tuple(f"/usr/{p}/" for p in (*FUNDIDAS, "libexec")) + tuple(f"/{p}/" for p in FUNDIDAS) + ("/boot/",)
ORDEM = {"alta": 0, "media": 1, "info": 2}
PASTAS_DE_BIBLIOTECAS = (f"/usr/lib/{os.uname().machine}-linux-gnu", f"/lib/{os.uname().machine}-linux-gnu",
                         "/usr/local/lib", "/usr/lib", "/lib", "/usr/lib64", "/lib64")

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


class Juiz:
    """O scanner de sempre, para julgar o conteúdo do que o caçador encontrar."""

    def __init__(self, banco=None, yara=None, clamav=None):
        self.banco, self.yara, self.clamav = banco, yara, clamav

    def __call__(self, caminho: Path) -> scanner.Resultado | None:
        if self.banco is None:
            return None
        # /proc/<pid>/exe é um link "mágico" para o executável, mesmo apagado do
        # disco. O ClamAV abre com O_NOFOLLOW e não passaria dele.
        clamav = None if str(caminho).startswith("/proc/") else self.clamav
        try:
            return scanner.analisar(caminho, self.banco, self.yara, clamav)
        except OSError:
            return None

    def comandos(self, comandos: list[str]) -> list[regras_yara.Ocorrencia]:
        """Comandos que o sistema vai executar sozinho são julgados como um script:
        as regras de `curl | sh` e base64 valem só para scripts (começam com #!)."""
        if self.yara is None or not comandos:
            return []
        texto = "#!/bin/sh\n" + "\n".join(comandos) + "\n"
        return [o for o in regras_yara.verificar_texto(texto, self.yara) if o.gravidade != "info"]


def cacar(julgar: Juiz | None = None, pacotes: Pacotes | None = None,
          casa: Path | None = None, conferir_pacotes: bool = True,
          olhar_comportamento: bool = True) -> list[Achado]:
    julgar = julgar or Juiz()
    pacotes = pacotes or Pacotes()
    lares = casas() if casa is None else [casa]
    achados = [
        *preload(pacotes),
        *ld_preload_em_processos(pacotes),
        *processos(julgar, pacotes),
        *persistencia(julgar, pacotes, locais_de_persistencia(casa or casa_real())),
        *(a for arquivo in arquivos_de_shell(lares) if (a := shell(arquivo, julgar, pacotes))),
        *chaves_autorizadas(lares, julgar),
        *(comportamento_agora() if olhar_comportamento else []),
        *(pacotes_alterados(julgar, dpkg_verify()) if conferir_pacotes else []),
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


def resolver_biblioteca(nome: str, ld_library_path: str) -> str:
    """Onde o ld.so acha uma biblioteca dada só pelo nome (ex.: o Firefox usa
    LD_PRELOAD=libmozsandbox.so): nas pastas do LD_LIBRARY_PATH, depois nas do sistema."""
    if "/" in nome:
        return nome
    for pasta in (*ld_library_path.split(":"), *PASTAS_DE_BIBLIOTECAS):
        if pasta and os.path.isfile(candidata := os.path.join(pasta, nome)):
            return candidata
    return nome


def ld_preload_em_processos(pacotes: Pacotes, proc: Path = PROC) -> Iterator[Achado]:
    """LD_PRELOAD faz o mesmo que o ld.so.preload, só para um processo e seus filhos."""
    por_lib: dict[str, list[str]] = {}
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        ambiente = _ler_ambiente(pid)
        for lib in ambiente.get("LD_PRELOAD", "").replace(":", " ").split():
            lib = resolver_biblioteca(lib, ambiente.get("LD_LIBRARY_PATH", ""))
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


def processos(julgar: Juiz | Julgar, pacotes: Pacotes, proc: Path = PROC) -> Iterator[Achado]:
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


# --- persistência: o que volta sozinho depois do reboot ---------------------

@dataclass
class Local:
    categoria: str        # "systemd", "cron", "autostart" ou "rc.local"
    caminho: Path         # arquivo ou pasta
    formato: str          # como achar os comandos: "systemd", "desktop", "cron-sistema", "cron-usuario", "script"


def locais_de_persistencia(casa: Path) -> list[Local]:
    sistema = [Path("/etc/systemd/system"), Path("/usr/lib/systemd/system"), Path("/etc/systemd/user"),
               Path("/usr/lib/systemd/user"), casa / ".config/systemd/user"]
    periodicos = [Path(f"/etc/cron.{p}") for p in ("hourly", "daily", "weekly", "monthly")]
    return [
        *(Local("systemd", p, "systemd") for p in sistema),
        Local("cron", Path("/etc/crontab"), "cron-sistema"),
        Local("cron", Path("/etc/cron.d"), "cron-sistema"),
        Local("cron", Path("/var/spool/cron/crontabs"), "cron-usuario"),   # só com root
        *(Local("cron", p, "script") for p in periodicos),
        Local("autostart", Path("/etc/xdg/autostart"), "desktop"),
        Local("autostart", casa / ".config/autostart", "desktop"),
        Local("rc.local", Path("/etc/rc.local"), "script"),
    ]


EXEC_SYSTEMD = re.compile(r"^\s*Exec(?:Start|StartPre|StartPost|Stop|StopPost|Reload)\s*=\s*(.+)$", re.MULTILINE)
EXEC_DESKTOP = re.compile(r"^\s*Exec\s*=\s*(.+)$", re.MULTILINE)
VARIAVEL = re.compile(r"^\w+\s*=")


def comandos(formato: str, texto: str) -> list[str]:
    """Os comandos que o sistema roda a partir de uma entrada de persistência."""
    if formato == "systemd":
        # Prefixos especiais do systemd: @ - : + ! (ex.: ExecStart=-/usr/bin/x).
        return [c.lstrip("@-:+!").strip() for c in EXEC_SYSTEMD.findall(texto)]
    if formato == "desktop":
        return [c.strip() for c in EXEC_DESKTOP.findall(texto)]
    if formato.startswith("cron"):
        saida = []
        campos_antes = 6 if formato == "cron-sistema" else 5   # 5 do horário (+ o usuário)
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or VARIAVEL.match(linha):
                continue
            if linha.startswith("@"):   # @reboot, @daily...: um campo de horário só
                campos_antes -= 4
            partes = linha.split(None, campos_antes)
            if len(partes) > campos_antes:
                saida.append(partes[campos_antes])
            campos_antes = 6 if formato == "cron-sistema" else 5
        return saida
    return []   # "script": o próprio arquivo é o que roda


def executavel(comando: str) -> str | None:
    """O programa que um comando chama: `env X=1 /opt/x --y` → /opt/x."""
    try:
        partes = shlex.split(comando)
    except ValueError:
        partes = comando.split()
    while partes and (partes[0] in ("env", "/usr/bin/env", "nohup", "exec") or VARIAVEL.match(partes[0])):
        partes.pop(0)
    if not partes:
        return None
    if partes[0].startswith("/"):
        return partes[0]
    return shutil.which(partes[0])


def _do_snap(nome: str, texto: str) -> bool:
    # O snapd gera as próprias unidades (snap-*.mount, snap.*.service) fora do dpkg.
    return nome.startswith(("snap-", "snap.")) and \
        ("X-Snappy=yes" in texto or "/usr/bin/snap run" in texto or "/var/lib/snapd/" in texto)


def _unidade_original(arquivo: Path, pacotes: Pacotes) -> Path | None:
    """A unidade de mesmo nome que veio de um pacote, se esta a sobrepõe."""
    for pasta in ("/usr/lib/systemd/system", "/usr/lib/systemd/user"):
        original = Path(pasta) / arquivo.name
        if original != arquivo and pacotes.dono(original):
            return original
    return None


def _arquivos(local: Local) -> Iterator[Path]:
    if local.caminho.is_file():
        yield local.caminho
        return
    for raiz, _dirs, nomes in os.walk(local.caminho):   # pasta sem permissão: pulada
        for nome in sorted(nomes):
            yield Path(raiz) / nome


def _crontab_do_usuario() -> str:
    """Sem root, /var/spool/cron é ilegível: o crontab -l mostra o do usuário."""
    if os.geteuid() == 0 or not shutil.which("crontab"):
        return ""
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def persistencia(julgar: Juiz, pacotes: Pacotes, locais: list[Local],
                 crontab_do_usuario: Callable[[], str] = _crontab_do_usuario) -> Iterator[Achado]:
    """Serviços, tarefas agendadas e programas de inicialização que não vieram de um pacote."""
    vistos: set[str] = set()
    for local in locais:
        for arquivo in _arquivos(local):
            real = os.path.realpath(arquivo)
            # Links em *.wants/ só "habilitam" uma unidade, que é avaliada uma vez.
            if real == "/dev/null" or real in vistos:
                continue   # /dev/null: unidade mascarada (desligada de propósito)
            vistos.add(real)
            if pacotes.dono(arquivo):
                continue
            try:
                texto = Path(real).read_text(errors="replace")
            except OSError:
                continue
            if _do_snap(arquivo.name, texto):
                continue
            achado = _avaliar(local.categoria, Path(real), comandos(local.formato, texto), julgar, pacotes,
                              formato=local.formato)
            if local.formato == "systemd" and (original := _unidade_original(Path(real), pacotes)):
                _comparar_com_original(achado, comandos("systemd", texto), original)
            yield achado

    if texto := crontab_do_usuario():
        cmds = comandos("cron-usuario", texto)
        if cmds:
            yield _avaliar("cron", Path("crontab -l"), cmds, julgar, pacotes, formato="cron-usuario",
                           julgar_arquivo=False)


def _comparar_com_original(achado: Achado, cmds: list[str], original: Path) -> None:
    # Trocar o ExecStart de uma unidade legítima (ex.: sshd.service) é um jeito
    # de ganhar persistência sem criar nenhum serviço novo.
    try:
        de_antes = comandos("systemd", original.read_text(errors="replace"))
    except OSError:
        return
    if cmds and cmds != de_antes:
        achado.gravidade = "alta" if achado.gravidade == "alta" else "media"
        achado.mensagem += f"\n           - troca o comando da unidade original ({original})"
    else:
        achado.mensagem += f"\n           - ajuste local de {original}, com o mesmo comando"


def _avaliar(categoria: str, arquivo: Path, cmds: list[str], julgar: Juiz, pacotes: Pacotes,
             formato: str, julgar_arquivo: bool = True) -> Achado:
    gravidade, notas = "info", []

    def subir(nova: str) -> None:
        nonlocal gravidade
        if ORDEM[nova] < ORDEM[gravidade]:
            gravidade = nova

    programas = {p for c in cmds if (p := executavel(c))}
    for programa in sorted(programas):
        if em_pasta_temporaria(programa):
            subir("alta")
            notas.append(f"roda {programa}, de uma pasta temporária")
        elif not os.path.exists(programa):
            notas.append(f"chama {programa}, que não existe mais")
    if any(re.search(r"(?<![\w.])/(?:tmp|var/tmp|dev/shm)/", c) for c in cmds) and gravidade == "info":
        subir("media")
        notas.append("o comando mexe numa pasta temporária")

    for o in julgar.comandos(cmds):
        subir(o.gravidade)
        notas.append(f"regra YARA {o.regra}: {o.descricao}")

    # O próprio arquivo (um script do cron, por exemplo) e os programas que ele chama.
    alvos = [arquivo] if julgar_arquivo else []
    alvos += [Path(p) for p in sorted(programas) if os.path.isfile(p) and not pacotes.dono(p)]
    for alvo in alvos:
        resultado = julgar(alvo)
        if resultado and resultado.infectado:
            subir("alta")
            notas.insert(0, f"{alvo}: {resultado.ameaca}")
        elif resultado and resultado.suspeito:
            subir("media")
            notas += [f"{alvo}: {m}" for m in resultado.motivos]

    if cmds:
        resumo = "; ".join(cmds)[:200]
    else:
        resumo = "o próprio arquivo é executado" if formato == "script" else "sem comando próprio"
    mensagem = f"não veio de um pacote · {resumo}"
    mensagem += "".join(f"\n           - {n}" for n in notas)
    return Achado(gravidade, categoria, arquivo, mensagem)


# --- binários do sistema alterados ------------------------------------------

def dpkg_verify() -> str:
    """Confere o MD5 de cada arquivo instalado com o que o pacote registrou (~30 s)."""
    if not shutil.which("dpkg"):
        return ""   # não é Debian/Ubuntu
    try:
        r = subprocess.run(["nice", "-n", "10", "dpkg", "--verify"], capture_output=True, text=True,
                           errors="replace", timeout=900)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout


def pacotes_alterados(julgar: Juiz | Julgar, saida: str) -> Iterator[Achado]:
    """Lê a saída do `dpkg --verify`: `??5??????   /usr/bin/ls` ou `??5?????? c /etc/x.conf`.

    Rootkits antigos trocavam o ls, o ps e o netstat por versões que escondem
    o invasor. A 3ª coluna "5" diz que o conteúdo já não é o que o pacote
    instalou; "?" diz que não deu para conferir (arquivo só legível pelo root).
    """
    sem_conferir = 0
    for linha in saida.splitlines():
        if len(linha) < 13 or linha.startswith("missing"):
            continue   # arquivo removido: comum em kernels antigos e caches
        marcas, configuracao, caminho = linha[:9], linha[10] == "c", linha[12:].strip()
        if marcas[2] == "?":
            sem_conferir += 1
            continue
        if marcas[2] != "5":
            continue
        if configuracao:
            yield Achado("info", "pacote alterado", Path(caminho),
                         "arquivo de configuração editado (normal se foi você ou um instalador)")
            continue
        gravidade = "alta" if caminho.startswith(EXECUTAVEIS) else "media"
        mensagem = "o conteúdo é diferente do que o pacote instalou"
        resultado = julgar(Path(caminho))
        if resultado and resultado.infectado:
            gravidade, mensagem = "alta", f"{resultado.ameaca} · {mensagem}"
        if gravidade == "alta":
            mensagem += "; confira com: sudo apt install --reinstall $(dpkg -S " + caminho + " | cut -d: -f1)"
        yield Achado(gravidade, "pacote alterado", Path(caminho), mensagem)
    if sem_conferir:
        yield Achado("info", "pacote alterado", Path("dpkg --verify"),
                     f"{sem_conferir} arquivos só legíveis pelo root ficaram sem conferir (rode com sudo)")


# --- arquivos de inicialização do shell -------------------------------------

DO_USUARIO = (".bashrc", ".bash_profile", ".bash_login", ".profile", ".bash_logout",
              ".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout")
DO_SISTEMA = (Path("/etc/profile"), Path("/etc/bash.bashrc"), Path("/etc/zsh/zshenv"),
              Path("/etc/zsh/zprofile"), Path("/etc/zsh/zshrc"), Path("/etc/zsh/zlogin"))
COMANDOS_DE_SENHA = r"(sudo|su|doas|passwd|ssh)"
ALIAS = re.compile(rf"^\s*alias\s+(?:-\w+\s+)*{COMANDOS_DE_SENHA}=(['\"]?)(.*)\2\s*$")
FUNCAO = re.compile(rf"^\s*(?:function\s+{COMANDOS_DE_SENHA}\b|{COMANDOS_DE_SENHA}\s*\(\s*\))")
EMBRULHOS = ("nocorrect", "noglob", "command", "builtin", "exec")   # ex.: alias sudo='nocorrect sudo'
PATH_TEMPORARIO = re.compile(r"\bPATH=.*(?<![\w.])(?:/tmp|/var/tmp|/dev/shm)(?:[/:\"']|$)")
LD_PRELOAD_EXPORTADO = re.compile(r"\bLD_PRELOAD=['\"]?([^'\"\s;]+)")
SOURCE = re.compile(r"(?:^|[;&|]|\bthen)\s*(?:source|\.)\s+['\"]?([^'\"\s;&|]+)")   # também `[ -f x ] && . x`


def casas() -> list[Path]:
    """Com root, a casa de todo usuário de verdade; sem root, só a sua."""
    if os.geteuid() != 0:
        return [casa_real()]
    lares = [Path("/root")]
    for u in pwd.getpwall():
        if u.pw_uid >= 1000 and u.pw_uid != 65534 and os.path.isdir(u.pw_dir):
            lares.append(Path(u.pw_dir))
    return lares


def arquivos_de_shell(lares: list[Path]) -> list[Path]:
    arquivos = [*DO_SISTEMA, *sorted(Path("/etc/profile.d").glob("*"))]
    arquivos += [casa / nome for casa in lares for nome in DO_USUARIO]
    return [a for a in arquivos if a.is_file()]


def _alias_suspeito(nome: str, valor: str) -> bool:
    palavras = valor.replace("\\", "").split()
    while palavras and palavras[0] in EMBRULHOS:
        palavras.pop(0)
    # alias sudo='sudo ' (o espaço faz o shell expandir aliases depois) é comum e inofensivo;
    # o mesmo nome em outra pasta (~/.local/.s/sudo) é justamente o truque.
    do_sistema = {nome, *(f"{pasta}/{nome}" for pasta in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"))}
    return not palavras or palavras[0] not in do_sistema


def _carregados(arquivo: Path, linhas: list[str], casa: Path) -> list[Path]:
    """Arquivos que este carrega com `source` ou `.`: um esconderijo a um passo."""
    saida = []
    for linha in linhas:
        for m in SOURCE.finditer(linha):
            alvo = m.group(1).replace("${HOME}", str(casa)).replace("$HOME", str(casa))
            alvo = str(casa) + alvo[1:] if alvo.startswith("~/") else alvo
            if "$" not in alvo and os.path.isfile(alvo) and Path(alvo) != arquivo:
                saida.append(Path(alvo))
    return saida


def _linhas_suspeitas(linhas: list[str], pacotes: Pacotes) -> list[tuple[str, str]]:
    notas = []
    for linha in linhas:
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        if (m := ALIAS.match(linha)) and _alias_suspeito(m.group(1), m.group(3)):
            notas.append(("media", f"redefine o {m.group(1)}, truque para capturar a senha: {linha.strip()}"))
        elif m := FUNCAO.match(linha):
            nome = next(g for g in m.groups() if g)
            notas.append(("media", f"troca o {nome} por uma função, truque para capturar a senha: {linha.strip()}"))
        if PATH_TEMPORARIO.search(linha):
            notas.append(("alta", f"põe uma pasta temporária no PATH: {linha.strip()}"))
        if m := LD_PRELOAD_EXPORTADO.search(linha):
            for lib in m.group(1).replace(":", " ").split():
                gravidade, motivo = _gravidade_da_biblioteca(lib, pacotes)
                notas.append(("media" if gravidade == "info" else gravidade, f"exporta LD_PRELOAD={lib}; {motivo}"))
        if (programa := executavel(linha.strip())) and em_pasta_temporaria(programa):
            notas.append(("alta", f"roda {programa}, de uma pasta temporária"))
    return notas


def shell(arquivo: Path, julgar: Juiz, pacotes: Pacotes) -> Achado | None:
    """Linhas com cara de ataque nos arquivos que todo terminal novo executa.

    Arquivos limpos não viram achado: o .bashrc é de cada um, e listar todos
    só esconderia o que importa.
    """
    casa = arquivo.parent if arquivo.name in DO_USUARIO else casa_real()
    notas: list[tuple[str, str]] = []
    vistos = [arquivo]
    try:
        linhas = arquivo.read_text(errors="replace").splitlines()
    except OSError:
        return None
    for alvo in _carregados(arquivo, linhas, casa):
        try:
            carregadas = alvo.read_text(errors="replace").splitlines()
        except OSError:
            continue
        vistos.append(alvo)
        notas += [(g, f"em {alvo}: {n}") for g, n in _linhas_suspeitas(carregadas, pacotes)]
        notas += [(o.gravidade, f"em {alvo}: regra YARA {o.regra}: {o.descricao}") for o in julgar.comandos(carregadas)]
    notas = _linhas_suspeitas(linhas, pacotes) + notas
    notas += [(o.gravidade, f"regra YARA {o.regra}: {o.descricao}") for o in julgar.comandos(linhas)]
    for alvo in vistos:
        if (resultado := julgar(alvo)) and resultado.infectado:
            notas.insert(0, ("alta", f"{alvo}: {resultado.ameaca}"))
    if not notas:
        return None
    gravidade = min((g for g, _ in notas), key=ORDEM.__getitem__)
    mensagem = "todo terminal novo executa este arquivo" + "".join(f"\n           - {n}" for _, n in notas)
    return Achado(gravidade, "shell", arquivo, mensagem)


# --- chaves SSH autorizadas -------------------------------------------------

MARCAS_DE_BOTNET = {"mdrfckr": "botnet Outlaw"}   # comentário que ela deixa na chave que acrescenta
RECENTE = 7 * 86400
CHAVE = re.compile(r"(?:^|\s)((?:ssh-|ecdsa-|sk-)\S+)\s+([A-Za-z0-9+/]+=*)(?:\s+(.*))?$")
PROC_TCP = (Path("/proc/net/tcp"), Path("/proc/net/tcp6"))


@dataclass
class Chave:
    opcoes: str           # ex.: command="...",no-pty
    tipo: str
    impressao: str        # como o ssh-keygen -l mostra: SHA256:...
    comentario: str


def ler_chave(linha: str) -> Chave | None:
    if not (m := CHAVE.search(linha)):
        return None
    try:
        bruto = base64.b64decode(m.group(2), validate=True)
        impressao = "SHA256:" + base64.b64encode(hashlib.sha256(bruto).digest()).decode().rstrip("=")
    except ValueError:
        impressao = "ilegível"
    return Chave(linha[:m.start(1)].strip(), m.group(1), impressao, (m.group(3) or "").strip())


def ssh_escutando(tabelas: tuple[Path, ...] = PROC_TCP) -> bool:
    """Alguém aceita conexões na porta 22? (estado 0A = LISTEN, porta em hexadecimal)"""
    for tabela in tabelas:
        try:
            linhas = tabela.read_text().splitlines()[1:]
        except OSError:
            continue
        if any(len(c := l.split()) > 3 and c[3] == "0A" and c[1].endswith(":0016") for l in linhas):
            return True
    return False


def chaves_autorizadas(lares: list[Path], julgar: Juiz, agora: float | None = None,
                       ssh_ligado: bool | None = None) -> Iterator[Achado]:
    """Quem tem a chave privada de uma destas entra como o usuário, sem senha.

    Botnets de mineração (Outlaw, Kinsing) acrescentam a própria chave para
    voltar quando quiserem. Arquivo vazio ou inexistente não vira achado.
    """
    agora = time.time() if agora is None else agora
    ssh_ligado = ssh_escutando() if ssh_ligado is None else ssh_ligado
    for casa in lares:
        for nome in ("authorized_keys", "authorized_keys2"):
            arquivo = casa / ".ssh" / nome
            try:
                linhas = arquivo.read_text(errors="replace").splitlines()
                mudou = arquivo.stat().st_mtime
            except OSError:
                continue
            chaves = [c for l in linhas if l.strip() and not l.lstrip().startswith("#") if (c := ler_chave(l))]
            if not chaves:
                continue
            gravidade, notas = "info", []
            for c in chaves:
                notas.append(f"{c.tipo} {c.impressao} {c.comentario or '(sem comentário)'}")
                marcas = f"{c.comentario} {c.opcoes}".lower()
                if botnet := next((b for marca, b in MARCAS_DE_BOTNET.items() if marca in marcas), None):
                    gravidade = "alta"
                    notas.append(f"  é a marca da {botnet}")
                if m := re.search(r'command="((?:[^"\\]|\\.)*)"', c.opcoes):
                    notas.append(f"  só pode rodar: {m.group(1)}")
                    for o in julgar.comandos([m.group(1)]):
                        gravidade = o.gravidade if ORDEM[o.gravidade] < ORDEM[gravidade] else gravidade
                        notas.append(f"  regra YARA {o.regra}: {o.descricao}")
            if agora - mudou < RECENTE and gravidade == "info":
                gravidade = "media"
                notas.insert(0, "o arquivo mudou nos últimos 7 dias: confira se foi você que acrescentou")
            estado = ("o SSH está ligado: quem tiver a chave privada entra" if ssh_ligado
                      else "o SSH está desligado: elas só valem se ele for ligado")
            mensagem = f"{len(chaves)} chave(s) entram como este usuário sem senha; {estado}"
            mensagem += "".join(f"\n           - {n}" for n in notas)
            yield Achado(gravidade, "ssh", arquivo, mensagem)


# --- comportamento ----------------------------------------------------------

def comportamento_agora() -> list[Achado]:
    """Uma olhada de 3 s no que os processos fazem (ver comportamento.py)."""
    from . import comportamento
    return [Achado(a.gravidade, a.tipo, Path(a.processo.exe), a.mensagem) for a in comportamento.examinar(3.0)]
