"""Olha dentro de .zip e .tar (inclusive .tar.gz/.bz2/.xz e zips dentro de zips).

Malware costuma chegar compactado justamente porque muitos antivírus não
abrem o pacote. Aqui cada membro passa pelo hash e pelo YARA, lido para a
memória: nada é extraído para o disco.

Defesa contra zip bomb: o tamanho declarado no cabeçalho pode ser mentira,
então o que vale é o que de fato sai da descompactação, somado num orçamento
único para o pacote inteiro (zips aninhados gastam do mesmo orçamento).
"""

import hashlib
import io
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import regras_yara

ORCAMENTO = 256 * 1024 * 1024    # bytes descompactados por pacote, somando tudo
MAX_MEMBRO = 32 * 1024 * 1024    # maior membro analisado
MAX_MEMBROS = 5000
MAX_PROFUNDIDADE = 3             # zip dentro de zip dentro de zip


INICIO_REGRAS = 64 * 1024   # quanto ler para reconhecer um arquivo de regras YARA


@dataclass
class Exame:
    ameaca: str | None = None
    camada: str | None = None
    pontuacao: int = 0
    motivos: list[str] = field(default_factory=list)
    membros: int = 0
    pulados: list[str] = field(default_factory=list)   # cifrados, grandes demais, estourou o orçamento


class _Orcamento:
    def __init__(self):
        self.restante = ORCAMENTO
        self.membros = 0


def tipo(cabecalho: bytes) -> str | None:
    if cabecalho.startswith(b"PK\x03\x04"):
        return "zip"
    if cabecalho[:2] == b"\x1f\x8b" or cabecalho[:3] == b"BZh" or cabecalho[:6] == b"\xfd7zXZ\x00":
        return "tar?"   # gzip/bzip2/xz: só um tar compactado nos interessa
    if len(cabecalho) >= 262 and cabecalho[257:262] == b"ustar":
        return "tar"
    return None


def examinar(caminho: Path, banco, yara=None) -> Exame | None:
    """None se não for um pacote. Senão, o que foi achado dentro dele."""
    with open(caminho, "rb") as f:
        cabecalho = f.read(512)
    if tipo(cabecalho) is None:
        return None
    exame = Exame()
    with open(caminho, "rb") as f:
        _abrir(f, cabecalho, "", banco, yara, exame, _Orcamento(), 1)
    return exame


def _abrir(arquivo, cabecalho, prefixo, banco, yara, exame, orcamento, profundidade) -> None:
    t = tipo(cabecalho)
    try:
        if t == "zip":
            with zipfile.ZipFile(arquivo) as z:
                membros = ((i.filename, i, z) for i in z.infolist() if not i.is_dir())
                _percorrer(membros, prefixo, banco, yara, exame, orcamento, profundidade)
        elif t is not None:
            with tarfile.open(fileobj=arquivo, mode="r:*") as tar:
                membros = ((m.name, m, tar) for m in tar if m.isreg())   # links e dispositivos: ignorados
                _percorrer(membros, prefixo, banco, yara, exame, orcamento, profundidade)
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, ValueError):
        pass   # .gz que não é tar, pacote corrompido: o arquivo em si já foi analisado


def _ler(origem, info, limite: int) -> bytes:
    if isinstance(origem, zipfile.ZipFile):
        with origem.open(info) as f:
            return f.read(limite + 1)
    f = origem.extractfile(info)
    return f.read(limite + 1) if f else b""


def _percorrer(membros, prefixo, banco, yara, exame, orcamento, profundidade) -> None:
    for nome, info, origem in membros:
        if exame.ameaca:
            return
        local = f"{prefixo}{nome}"
        if orcamento.membros >= MAX_MEMBROS or orcamento.restante <= 0:
            exame.pulados.append(f"{local} (limite do pacote)")
            return
        if isinstance(info, zipfile.ZipInfo) and info.flag_bits & 0x1:
            exame.pulados.append(f"{local} (cifrado)")
            continue
        orcamento.membros += 1
        if isinstance(info, tarfile.TarInfo):
            # Num tar compactado, passar para o próximo membro obriga a descompactar
            # este inteiro, lido ou não. O tamanho no cabeçalho do tar é sempre o
            # verdadeiro (o formato depende dele), então já sai do orçamento.
            if info.size > orcamento.restante:
                exame.pulados.append(f"{local} (limite do pacote)")
                return
            orcamento.restante -= info.size
            limite = min(MAX_MEMBRO, info.size)
        else:
            limite = min(MAX_MEMBRO, orcamento.restante)
        try:
            dados = _ler(origem, info, limite)
        except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, RuntimeError, ValueError):
            exame.pulados.append(f"{local} (ilegível)")
            continue
        if isinstance(info, zipfile.ZipInfo):
            orcamento.restante -= len(dados)   # no zip, só vale o que de fato saiu
        if len(dados) > limite:
            exame.pulados.append(f"{local} (grande demais)")
            continue
        exame.membros += 1
        _analisar_membro(dados, local, banco, yara, exame)
        if not exame.ameaca and profundidade < MAX_PROFUNDIDADE and tipo(dados[:512]):
            _abrir(io.BytesIO(dados), dados[:512], f"{local}/", banco, yara, exame, orcamento, profundidade + 1)


def _analisar_membro(dados: bytes, local: str, banco, yara, exame: Exame) -> None:
    if nome := banco.get(hashlib.sha256(dados).hexdigest()):
        exame.ameaca, exame.camada = f"{nome} (dentro: {local})", "hash"
        return
    if yara is None or regras_yara.e_arquivo_de_regras(local, dados[:INICIO_REGRAS]):
        return
    for o in regras_yara.verificar_bytes(dados, yara):
        if o.gravidade == "alta":
            exame.ameaca, exame.camada = f"{o.regra} (YARA, dentro: {local})", "yara"
            return
        if o.gravidade == "media":
            exame.camada = exame.camada or "yara"
            exame.pontuacao += regras_yara.PESO_MEDIA
            exame.motivos.append(f"regra YARA {o.regra} em {local}: {o.descricao}")
