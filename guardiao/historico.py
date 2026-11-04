"""Histórico de varreduras: uma linha JSON por varredura.

Responde "quando foi a última varredura completa?" e guarda o que cada uma
achou, para o launcher oferecer trancar depois o que uma varredura agendada
encontrou de madrugada.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .caminhos import casa_real

ARQUIVO = Path(os.environ.get("XDG_DATA_HOME", casa_real() / ".local" / "share")) / "guardiao" / "historico.jsonl"
MAX_ACHADOS = 200          # por varredura: um disco cheio de suspeitos não incha o arquivo
MAX_REGISTROS = 500        # ~1 ano e meio de varreduras diárias; as mais antigas saem


@dataclass
class Registro:
    inicio: str                      # ISO 8601, horário local
    tipo: str                        # "rápida", "completa" ou o caminho varrido
    origem: str                      # "terminal", "agendada" ou "launcher"
    segundos: float = 0.0
    total: int = 0
    analisados: int = 0
    em_cache: int = 0
    ameacas: int = 0
    suspeitos: int = 0
    sem_permissao: int = 0
    grandes: int = 0
    root: bool = False
    achados: list[dict] = field(default_factory=list)

    @property
    def quando(self) -> datetime:
        return datetime.fromisoformat(self.inicio)


def achado(resultado, quarentena: str | None = None) -> dict:
    """O que guardar de um scanner.Resultado."""
    return {
        "caminho": str(resultado.caminho),
        "veredito": "ameaca" if resultado.infectado else "suspeito",
        "ameaca": resultado.ameaca,
        "camada": resultado.camada,
        "pontuacao": resultado.pontuacao,
        "motivos": resultado.motivos[:3],
        "sha256": resultado.sha256,
        "quarentena": quarentena,
    }


def novo(tipo: str, origem: str, inicio: datetime, resumo, achados: list[dict]) -> Registro:
    return Registro(
        inicio=inicio.isoformat(timespec="seconds"), tipo=tipo, origem=origem,
        segundos=round(resumo.segundos, 1), total=resumo.analisados + resumo.em_cache,
        analisados=resumo.analisados, em_cache=resumo.em_cache, ameacas=resumo.ameacas,
        suspeitos=resumo.suspeitos, sem_permissao=resumo.sem_permissao, grandes=resumo.grandes,
        root=os.geteuid() == 0,
        # Ameaças primeiro: se precisar cortar, cortam-se suspeitos.
        achados=sorted(achados, key=lambda a: a["veredito"] != "ameaca")[:MAX_ACHADOS],
    )


def registrar(registro: Registro, arquivo: Path | None = None) -> None:
    """Acrescenta uma linha. Nunca quebra a varredura: o histórico é um extra."""
    arquivo = arquivo or ARQUIVO
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(registro), ensure_ascii=False) + "\n")
        _podar(arquivo)
        _devolver_ao_usuario(arquivo)
    except OSError:
        pass


def _podar(arquivo: Path) -> None:
    linhas = arquivo.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(linhas) <= MAX_REGISTROS:
        return
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text("".join(linhas[-MAX_REGISTROS:]), encoding="utf-8")
    temporario.replace(arquivo)    # troca de uma vez: quem lê nunca vê metade


def _devolver_ao_usuario(arquivo: Path) -> None:
    # Com sudo, o arquivo nasceria do root dentro da sua casa, e a próxima
    # varredura sem sudo não conseguiria mais escrever nele.
    if os.geteuid() == 0 and (uid := os.environ.get("SUDO_UID")) and (gid := os.environ.get("SUDO_GID")):
        for caminho in (arquivo.parent, arquivo):
            os.chown(caminho, int(uid), int(gid))


def listar(limite: int | None = 20, arquivo: Path | None = None) -> list[Registro]:
    """Os registros mais recentes primeiro. Linhas estragadas são puladas."""
    arquivo = arquivo or ARQUIVO
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    registros = []
    for linha in reversed(linhas):
        try:
            registros.append(Registro(**json.loads(linha)))
        except (ValueError, TypeError):
            continue
        if limite is not None and len(registros) >= limite:
            break
    return registros


def ultima(tipo: str, arquivo: Path | None = None) -> Registro | None:
    return next((r for r in listar(None, arquivo) if r.tipo == tipo), None)


def marcar_isolado(caminho: str, sha256: str, quarentena: str, arquivo: Path | None = None) -> None:
    """Anota a quarentena nos achados daquele arquivo, para ele não aparecer mais como pendente."""
    arquivo = arquivo or ARQUIVO
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    novas = []
    for linha in linhas:
        try:
            dados = json.loads(linha)
            for a in dados.get("achados", []):
                if a.get("caminho") == caminho and a.get("sha256") == sha256 and not a.get("quarentena"):
                    a["quarentena"] = quarentena
            novas.append(json.dumps(dados, ensure_ascii=False))
        except (ValueError, AttributeError):
            novas.append(linha)
    temporario = arquivo.with_suffix(".tmp")
    try:
        temporario.write_text("\n".join(novas) + "\n", encoding="utf-8")
        temporario.replace(arquivo)
    except OSError:
        pass


def pendentes(registros: list[Registro]) -> list[tuple[Registro, dict]]:
    """Ameaças achadas que ainda estão no lugar: sem quarentena e o arquivo existe.
    Um por caminho, o achado mais recente."""
    vistos, lista = set(), []
    for r in registros:
        for a in r.achados:
            if a.get("veredito") != "ameaca" or a.get("quarentena") or a["caminho"] in vistos:
                continue
            vistos.add(a["caminho"])
            if os.path.isfile(a["caminho"]) and not os.path.islink(a["caminho"]):
                lista.append((r, a))
    return lista
