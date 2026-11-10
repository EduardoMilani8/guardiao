"""O que o escudo da barra do GNOME mostra (guarnicao-design: telas/barra-v2.html).

Um estado só, na ordem de prioridade: ameaça não tratada > procurando >
precisa de atenção > tudo certo. Só lê; quem age são os botões do menu.
"""

import math
from datetime import datetime

from . import historico, notificacao


def quando(instante: datetime, agora: datetime) -> str:
    dias = (agora.date() - instante.date()).days
    dia = "hoje" if dias == 0 else "ontem" if dias == 1 else instante.strftime("%d/%m")
    return f"{dia}, {instante:%H:%M}"


def ha_quanto(segundos: float) -> str:
    if segundos < 3600:
        return f"há {max(1, int(segundos // 60))} min"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    return f"há {int(segundos // 86400)} dia(s)"


def _ultima(registros: list, agora: datetime) -> list[str]:
    if not registros:
        return ["Nenhuma varredura ainda"]
    r = registros[0]
    return [f"Última: {r.tipo} · {quando(r.quando, agora)}"]


def montar(servicos: dict, registros: list, progresso: dict | None, agora: datetime) -> dict:
    perigosos = historico.pendentes(registros)
    if perigosos:
        n = len(perigosos)
        titulo = "1 arquivo perigoso" if n == 1 else f"{n} arquivos perigosos"
        r, _ = perigosos[0]
        return {"estado": "ameaca", "titulo": titulo,
                "linhas": [notificacao.contar_achados(n, 0), f"Varredura {r.tipo} · {quando(r.quando, agora)}"],
                "acoes": ["trancar", "varrer"]}

    if progresso and progresso.get("total"):
        feitos, total = progresso["feitos"], progresso["total"]
        pct = min(100, round(100 * feitos / total))
        return {"estado": "procurando", "titulo": "Procurando ameaças…", "nivel": max(1, math.ceil(pct / 25)),
                "pct": pct,
                "linhas": [f"{feitos} de {total} arquivos · {pct}%", "Nada encontrado até agora"],
                "acoes": ["abrir", "parar"] if progresso.get("pode_parar") else ["abrir"]}

    bases = servicos.get("bases", {})
    if bases.get("avisos") or bases.get("freshclam_parado"):
        linhas = list(bases.get("avisos") or [])[:2] or ["O serviço do ClamAV (freshclam) está parado"]
        clamd_parado = any(a.startswith("clamav: o clamd") for a in linhas)
        titulo = "O ClamAV está parado" if clamd_parado else "Suas bases estão desatualizadas"
        return {"estado": "atencao", "titulo": titulo, "linhas": linhas,
                "acoes": ["atualizar", "abrir"]}
    for nome, rotulo in (("protetor", "O protetor está desligado"), ("monitor", "O monitor está desligado")):
        s = servicos.get(nome, {})
        if s.get("instalado") and not s.get("ativo"):
            return {"estado": "atencao", "titulo": rotulo, "linhas": [f"Para ligar: {s.get('ligar', '')}"],
                    "acoes": ["abrir"]}

    linhas = _ultima(registros, agora)
    if bases.get("conferidas"):
        linhas.append(f"Bases atualizadas {ha_quanto(agora.timestamp() - bases['conferidas'])}")
    return {"estado": "certo", "titulo": "Você está protegido", "linhas": linhas, "acoes": ["varrer", "abrir"]}
