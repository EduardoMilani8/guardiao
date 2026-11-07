"""O que o painel mostra em "Em segundo plano": serviços, bases e agendas.

Tudo aqui só lê: o painel roda sem root e não liga nem desliga serviço nenhum.
Quando algo está parado, ele mostra o comando para a pessoa rodar.
"""

import subprocess
import time

from .. import bases

PROTETOR = "guarnicao-protetor.service"      # serviço do sistema (root)
MONITOR = "guarnicao-monitor.service"         # serviços do usuário
TIMERS = {"rapida": "guarnicao-varrer-rapida.timer", "completa": "guarnicao-varrer-completa.timer",
          "atualizar": "guarnicao-atualizar.timer"}
LIGAR_PROTETOR = "sudo systemctl enable --now guarnicao-protetor"
LIGAR_MONITOR = "systemctl --user enable --now guarnicao-monitor"


def _systemctl(unidade: str, usuario: bool, campos: list[str]) -> dict[str, str]:
    comando = ["systemctl", *(["--user"] if usuario else []), "show", "--timestamp=unix",
               unidade, *(f"--property={c}" for c in campos)]
    try:
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    campos_lidos = {}
    for linha in saida.splitlines():
        chave, _, valor = linha.partition("=")
        campos_lidos[chave] = valor
    return campos_lidos


def _instante(valor: str | None) -> float | None:
    """'@1794060984' (systemctl --timestamp=unix) → 1794060984.0; vazio → None."""
    return float(valor[1:]) if valor and valor.startswith("@") and valor[1:].isdigit() else None


def servico(unidade: str, usuario: bool, ler=_systemctl) -> dict:
    """{"instalado", "ativo", "desde"}: desde quando está no estado atual."""
    d = ler(unidade, usuario, ["LoadState", "ActiveState", "ActiveEnterTimestamp", "InactiveEnterTimestamp"])
    if not d or d.get("LoadState") == "not-found":
        return {"instalado": False, "ativo": False, "desde": None}
    ativo = d.get("ActiveState") == "active"
    desde = _instante(d.get("ActiveEnterTimestamp" if ativo else "InactiveEnterTimestamp"))
    return {"instalado": True, "ativo": ativo, "desde": desde}


def proxima(timer: str, ler=_systemctl) -> float | None:
    return _instante(ler(timer, True, ["NextElapseUSecRealtime"]).get("NextElapseUSecRealtime"))


def estado_das_bases(agora: float | None = None) -> dict:
    """Quando as bases foram conferidas pela última vez. As que ficaram velhas
    demais aparecem em `avisos`; aqui vale a conferência mais recente."""
    lista = bases.registradas()
    conferidas = [e.verificado for e in map(bases.ler_estado, lista)]
    datas = [c for c in conferidas if c is not None]
    return {
        "conferidas": max(datas) if datas else None,
        "avisos": bases.avisos(agora=agora),
        "freshclam_parado": bases.freshclam_parado(),
        "ligar_freshclam": bases.LIGAR_FRESHCLAM,
    }


def montar(ler=_systemctl) -> dict:
    return {
        "agora": time.time(),
        "protetor": servico(PROTETOR, False, ler) | {"ligar": LIGAR_PROTETOR},
        "monitor": servico(MONITOR, True, ler) | {"ligar": LIGAR_MONITOR},
        "proximas": {nome: proxima(timer, ler) for nome, timer in TIMERS.items()},
        "bases": estado_das_bases(),
    }
