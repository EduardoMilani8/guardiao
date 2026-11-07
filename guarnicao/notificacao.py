"""Notificações nativas da área de trabalho (libnotify / notify-send)."""

import os
import pwd
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .caminhos import casa_real

RUN_USER = Path("/run/user")
# Data do último resumo de varredura limpa: no máximo um por dia.
MARCA_RESUMO = Path(os.environ.get("XDG_CACHE_HOME", casa_real() / ".cache")) / "guarnicao" / "ultimo-resumo"


def _sessoes(raiz: Path = RUN_USER) -> list[tuple[int, int, Path]]:
    """(uid, gid, barramento) de cada usuário com sessão aberta."""
    sessoes = []
    for pasta in sorted(raiz.glob("[0-9]*")):
        barramento = pasta / "bus"
        if int(pasta.name) < 1000 or not barramento.exists():
            continue
        try:
            sessoes.append((int(pasta.name), pwd.getpwuid(int(pasta.name)).pw_gid, barramento))
        except KeyError:
            continue
    return sessoes


def comando(titulo: str, corpo: str, urgente: bool = False, discreto: bool = False) -> list[str]:
    # Lista de argumentos, sem shell: um nome de arquivo malicioso como
    # "$(rm -rf ~).pdf" vira texto na notificação, nunca um comando.
    if discreto:
        # Tudo bem: some sozinho em poucos segundos e não fica guardado na lista.
        # Urgência normal, não baixa: o GNOME nunca mostra balão de urgência baixa
        # (messageTray.js, _onNotificationRequestBanner), e com --transient o aviso
        # nem iria para a lista: não apareceria em lugar nenhum.
        opcoes = ["--urgency", "normal", "--icon", "security-high", "--transient", "--expire-time", "6000"]
    else:
        opcoes = ["--urgency", "critical" if urgente else "normal",
                  "--icon", "security-low" if urgente else "dialog-warning"]
    return ["notify-send", "--app-name=Guarnição", *opcoes, titulo, corpo]


def texto_resumo_limpo(nome: str, total: int, quando: datetime) -> tuple[str, str]:
    """O texto do aviso de varredura limpa, igual ao desenho (avisos-v3-muralha)."""
    arquivos = f"{total:,}".replace(",", ".")
    return f"Varredura {nome} concluída ✓", f"{arquivos} arquivos, tudo limpo · hoje, {quando:%H:%M}"


def resumo_limpo(nome: str, total: int, quando: datetime, marca: Path | None = None) -> bool:
    """Avisa que a varredura agendada terminou limpa, no máximo uma vez por dia.

    Devolve True se avisou. O resto do tempo, o silêncio é o aviso: quem lembra
    que a Guarnição está ali é o escudo da barra, não uma pilha de notificações.
    """
    marca = marca or MARCA_RESUMO
    hoje = quando.date().isoformat()
    try:
        if marca.read_text().strip() == hoje:
            return False
    except OSError:
        pass
    notificar(*texto_resumo_limpo(nome, total, quando), discreto=True)
    try:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(hoje)
    except OSError:
        pass   # sem onde guardar: no pior caso avisa de novo amanhã cedo, nunca quebra a varredura
    return True


def notificar(titulo: str, corpo: str, urgente: bool = False, discreto: bool = False) -> None:
    """Mostra uma notificação; não faz nada se notify-send não existir.

    Como root (o protetor é um serviço do sistema), não há área de trabalho
    própria: a notificação vai para a sessão de cada usuário, rodando o
    notify-send como ele, nunca como root.
    """
    if shutil.which("notify-send") is None:
        return
    if os.geteuid() != 0:
        subprocess.run(comando(titulo, corpo, urgente, discreto), check=False)
        return
    for uid, gid, barramento in _sessoes():
        try:
            subprocess.run(
                ["setpriv", f"--reuid={uid}", f"--regid={gid}", "--clear-groups",
                 "env", f"DBUS_SESSION_BUS_ADDRESS=unix:path={barramento}", *comando(titulo, corpo, urgente, discreto)],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
        except subprocess.TimeoutExpired:
            pass
