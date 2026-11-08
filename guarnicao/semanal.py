"""A varredura completa da semana, sem atrapalhar quem está usando o PC.

Em 08/11/2026 a completa de domingo começou sozinha no meio de um jogo e, somada
a ele, a memória acabou. Agora um timer confere de meia em meia hora: se a
completa da semana ainda não foi feita, ela começa sozinha só com o PC parado
há 15 min e na tomada; fora isso, pergunta (no máximo uma vez por dia).
"""

import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .notificacao import MARCA_RESUMO

PARADO_MS = 15 * 60 * 1000
SEMANA = timedelta(days=7)
FONTES = Path("/sys/class/power_supply")


def devida(registros: list, agora: datetime) -> bool:
    """True se não houve varredura completa nos últimos 7 dias."""
    return not any(r.tipo == "completa" and agora - r.quando < SEMANA for r in registros)


def decidir(devida: bool, ocioso_ms: int | None, na_tomada: bool, perguntou_hoje: bool) -> str:
    """ "rodar", "perguntar" ou "nada"."""
    if not devida:
        return "nada"
    if na_tomada and ocioso_ms is not None and ocioso_ms >= PARADO_MS:
        return "rodar"
    return "nada" if perguntou_hoje else "perguntar"


def na_tomada(fontes: Path = FONTES) -> bool:
    """Ligado no carregador? Sem bateria (um desktop), sempre."""
    tipos = {}
    for d in fontes.glob("*"):
        try:
            tipos[d] = (d / "type").read_text().strip()
        except OSError:
            continue
    if "Battery" not in tipos.values():
        return True
    for d, tipo in tipos.items():
        if tipo == "Mains":
            try:
                if (d / "online").read_text().strip() == "1":
                    return True
            except OSError:
                pass
    return False


def ocioso_ms() -> int | None:
    """Há quanto tempo ninguém mexe no teclado e no mouse, segundo o GNOME."""
    try:
        saida = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor",
             "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
             "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
            capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    numero = re.search(r"uint64 (\d+)", saida.stdout or "")
    return int(numero.group(1)) if saida.returncode == 0 and numero else None


MARCA = MARCA_RESUMO.with_name("ultima-pergunta-completa")
SERVICO = "guarnicao-varrer-completa.service"


def perguntou_hoje(agora: datetime, marca: Path | None = None) -> bool:
    try:
        return (marca or MARCA).read_text().strip() == agora.date().isoformat()
    except OSError:
        return False


def iniciar() -> None:
    """Começa a completa pelo serviço, com o teto de memória e a prioridade baixa dele."""
    subprocess.run(["systemctl", "--user", "start", "--no-block", SERVICO], check=False)
