"""Notificações nativas da área de trabalho (libnotify / notify-send)."""

import shutil
import subprocess


def notificar(titulo: str, corpo: str, urgente: bool = False) -> None:
    """Mostra uma notificação; não faz nada se notify-send não existir."""
    if shutil.which("notify-send") is None:
        return
    # Lista de argumentos, sem shell: um nome de arquivo malicioso como
    # "$(rm -rf ~).pdf" vira texto na notificação, nunca um comando.
    subprocess.run(
        [
            "notify-send",
            "--app-name=Guardião",
            "--urgency", "critical" if urgente else "normal",
            "--icon", "security-low" if urgente else "dialog-warning",
            titulo,
            corpo,
        ],
        check=False,
    )
