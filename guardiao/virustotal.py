"""VirusTotal: o que uns 70 antivírus acham de um arquivo, consultado pelo hash.

Opcional e desligado por padrão. Para ligar, crie uma conta grátis em
https://www.virustotal.com e coloque a chave da API no ~/.config/guardiao/config.toml:

    [virustotal]
    chave = "..."

Só o SHA-256 sai do computador, nunca o arquivo. Mesmo assim, cada consulta
conta ao VirusTotal que aquele hash existe aqui: por isso a consulta é feita só
para downloads novos (monitor), para arquivos que a varredura já achou
suspeitos e quando você pede (`guardiao virustotal <arquivo>`).

A chave grátis permite 4 consultas por minuto e 500 por dia. As respostas ficam
num cache, e a cota é contada num arquivo com trava: o monitor e uma varredura
rodando juntos dividem o mesmo limite.
"""

import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__, heuristicas
from .caminhos import casa_real, ler_config

API = "https://www.virustotal.com/api/v3/files/{}"
ARQUIVO = Path(os.environ.get("XDG_CACHE_HOME", casa_real() / ".cache")) / "guardiao" / "virustotal.json"
POR_MINUTO = 4
POR_DIA = 500
MINIMO_AMEACA = 5          # antivírus dizendo "malicioso" para virar ameaça
MINIMO_SUSPEITO = 2        # um só costuma ser alarme falso daquele antivírus
VALIDADE_CONHECIDO = 7 * 86400
VALIDADE_DESCONHECIDO = 86400   # um arquivo novo pode ser enviado amanhã
TEMPO_LIMITE = 15


class SemCota(Exception):
    """O limite da chave grátis acabou por agora. `espera`: segundos até abrir
    vaga no limite por minuto; None quando o que acabou foi a cota do dia."""

    def __init__(self, mensagem: str, espera: float | None = None):
        super().__init__(mensagem)
        self.espera = espera


@dataclass
class Laudo:
    maliciosos: int
    total: int                 # 0: o VirusTotal nunca viu este arquivo
    nome: str | None = None    # rótulo sugerido, ex.: "trojan.mirai/gafgyt"

    @property
    def conhecido(self) -> bool:
        return self.total > 0


def chave() -> str | None:
    return os.environ.get("GUARDIAO_VIRUSTOTAL_CHAVE") or \
        ler_config().get("virustotal", {}).get("chave") or None


def _pedir(sha256: str, chave_api: str) -> Laudo:
    pedido = urllib.request.Request(API.format(sha256), headers={
        "x-apikey": chave_api, "User-Agent": f"guardiao/{__version__}"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            atributos = json.load(resposta)["data"]["attributes"]
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            return Laudo(0, 0)
        if erro.code == 429:
            raise SemCota("o VirusTotal recusou: limite da chave atingido") from None
        raise OSError(f"VirusTotal respondeu {erro.code}") from None
    estatisticas = atributos.get("last_analysis_stats", {})
    rotulo = (atributos.get("popular_threat_classification") or {}).get("suggested_threat_label")
    return Laudo(maliciosos=estatisticas.get("malicious", 0),
                 total=sum(v for v in estatisticas.values() if isinstance(v, int)),
                 nome=rotulo)


class _Registro:
    """O arquivo de cache, aberto com trava exclusiva enquanto dura o `with`."""

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo

    def __enter__(self) -> dict:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self.arquivo.with_suffix(".trava"), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        try:
            self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.dados = {}
        self.dados.setdefault("consultas", [])
        self.dados.setdefault("hashes", {})
        return self.dados

    def __exit__(self, *_):
        try:
            temporario = self.arquivo.with_suffix(".tmp")
            temporario.write_text(json.dumps(self.dados), encoding="utf-8")
            temporario.replace(self.arquivo)
        finally:
            os.close(self._fd)   # solta a trava


def consultar(sha256: str, chave_api: str, arquivo: Path | None = None,
              agora: float | None = None, pedir=_pedir) -> Laudo:
    """O laudo do VirusTotal, do cache se for recente. SemCota se o limite acabou;
    OSError se a rede ou o servidor falharem."""
    arquivo = arquivo or ARQUIVO
    agora = time.time() if agora is None else agora
    with _Registro(arquivo) as dados:
        if (guardado := dados["hashes"].get(sha256)) is not None:
            validade = VALIDADE_CONHECIDO if guardado["total"] else VALIDADE_DESCONHECIDO
            if agora - guardado["quando"] < validade:
                return Laudo(guardado["maliciosos"], guardado["total"], guardado.get("nome"))
        dados["consultas"] = [t for t in dados["consultas"] if agora - t < 86400]
        ultimo_minuto = [t for t in dados["consultas"] if agora - t < 60]
        if len(ultimo_minuto) >= POR_MINUTO:
            raise SemCota(f"limite de {POR_MINUTO} consultas por minuto", espera=60 - (agora - min(ultimo_minuto)))
        if len(dados["consultas"]) >= POR_DIA:
            raise SemCota(f"limite de {POR_DIA} consultas por dia")
        dados["consultas"].append(agora)   # conta antes: uma falha de rede também gasta a cota

    laudo = pedir(sha256, chave_api)

    with _Registro(arquivo) as dados:
        dados["hashes"][sha256] = {"quando": agora, "maliciosos": laudo.maliciosos,
                                   "total": laudo.total, "nome": laudo.nome}
        # Não deixa o cache crescer para sempre: só o que ainda vale.
        dados["hashes"] = {s: h for s, h in dados["hashes"].items()
                           if agora - h["quando"] < VALIDADE_CONHECIDO}
    return laudo


def aplicar(resultado, laudo: Laudo):
    """Junta o laudo ao Resultado do scanner. Nunca rebaixa uma ameaça."""
    if resultado.infectado or not laudo.conhecido:
        return resultado
    placar = f"{laudo.maliciosos} de {laudo.total} antivírus"
    if laudo.maliciosos >= MINIMO_AMEACA:
        resultado.ameaca = f"{laudo.nome or 'malicioso'} (VirusTotal, {placar})"
        resultado.camada = "virustotal"
    elif laudo.maliciosos >= MINIMO_SUSPEITO:
        resultado.pontuacao = max(resultado.pontuacao, heuristicas.LIMIAR_SUSPEITO)
        resultado.motivos.append(f"VirusTotal: {placar} apontam como malicioso")
        resultado.camada = resultado.camada or "virustotal"
    elif laudo.maliciosos == 1:
        resultado.motivos.append(f"VirusTotal: {placar} aponta como malicioso")
    return resultado
