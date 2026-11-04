"""Notificações nativas da área de trabalho (libnotify / notify-send)."""

import os
import pwd
import shutil
import subprocess
from pathlib import Path

RUN_USER = Path("/run/user")


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


def comando(titulo: str, corpo: str, urgente: bool = False) -> list[str]:
    # Lista de argumentos, sem shell: um nome de arquivo malicioso como
    # "$(rm -rf ~).pdf" vira texto na notificação, nunca um comando.
    return [
        "notify-send",
        "--app-name=Guardião",
        "--urgency", "critical" if urgente else "normal",
        "--icon", "security-low" if urgente else "dialog-warning",
        titulo,
        corpo,
    ]


def notificar(titulo: str, corpo: str, urgente: bool = False) -> None:
    """Mostra uma notificação; não faz nada se notify-send não existir.

    Como root (o protetor é um serviço do sistema), não há área de trabalho
    própria: a notificação vai para a sessão de cada usuário, rodando o
    notify-send como ele, nunca como root.
    """
    if shutil.which("notify-send") is None:
        return
    if os.geteuid() != 0:
        subprocess.run(comando(titulo, corpo, urgente), check=False)
        return
    for uid, gid, barramento in _sessoes():
        try:
            subprocess.run(
                ["setpriv", f"--reuid={uid}", f"--regid={gid}", "--clear-groups",
                 "env", f"DBUS_SESSION_BUS_ADDRESS=unix:path={barramento}", *comando(titulo, corpo, urgente)],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
        except subprocess.TimeoutExpired:
            pass
