"""Bases de detecção baixadas da internet e mantidas em dia.

Cada base fica numa pasta própria, com uma subpasta por versão e um link
`atual` apontando para a que está valendo:

    bases/yara-forge/versoes/20261103-140000/...
    bases/yara-forge/atual -> versoes/20261103-140000
    bases/yara-forge/estado.json

A versão nova é baixada e validada à parte; só então o link é trocado, num
passo atômico (os.replace). Se o download cair ou a base vier quebrada, a
versão anterior continua valendo: uma atualização ruim nunca deixa a
Guarnição sem proteção.
"""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .caminhos import casa_real

PASTA = Path(os.environ.get("XDG_DATA_HOME", casa_real() / ".local" / "share")) / "guarnicao" / "bases"
LIMITE_DOWNLOAD = 512 * 1024 * 1024
VERSOES_GUARDADAS = 2      # a atual e a anterior, para poder voltar atrás
VELHA_APOS = 2 * 24 * 3600


class ErroDeBase(Exception):
    """O download ou a validação falhou; a versão anterior segue valendo."""


class Ocupado(Exception):
    """Outra atualização já está rodando."""


class Base:
    """Uma fonte de detecção. Subclasses implementam `baixar` e `validar`."""

    nome = ""
    descricao = ""
    intervalo = 3600           # segundos entre tentativas
    invalida_cache = True      # versão nova muda vereditos: o cache recomeça

    def baixar(self, destino: Path, versao_atual: str | None) -> str | None:
        """Preenche `destino` e devolve o id da versão (ex.: data de publicação).
        Devolve None se a versão publicada ainda é `versao_atual` (nada a baixar)."""
        raise NotImplementedError

    def validar(self, pasta: Path) -> None:
        """Levanta ErroDeBase se a pasta baixada não estiver boa para uso."""


@dataclass
class Estado:
    versao: str | None = None
    atualizado: float | None = None    # quando a versão atual entrou
    verificado: float | None = None    # última vez que confirmamos estar em dia
    tentativa: float | None = None
    erro: str | None = None

    def idade(self, agora: float | None = None) -> float | None:
        """Segundos desde a última confirmação de que a base está em dia."""
        return None if self.verificado is None else (agora or time.time()) - self.verificado


@dataclass
class Relatorio:
    base: str
    situacao: str              # "atualizada", "em dia", "sem novidades" ou "erro"
    estado: Estado = field(default_factory=Estado)


def pasta_da(base: Base | str) -> Path:
    return PASTA / (base if isinstance(base, str) else base.nome)


def atual(base: Base | str) -> Path | None:
    """Pasta da versão que está valendo, ou None se a base nunca foi baixada."""
    link = pasta_da(base) / "atual"
    return link.resolve() if link.is_dir() else None


def ler_estado(base: Base | str) -> Estado:
    try:
        return Estado(**json.loads((pasta_da(base) / "estado.json").read_text()))
    except (OSError, ValueError, TypeError):
        return Estado()


def _gravar_estado(base: Base, estado: Estado) -> None:
    arquivo = pasta_da(base) / "estado.json"
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado.__dict__, indent=2))
    os.replace(tmp, arquivo)


@contextmanager
def trava():
    PASTA.mkdir(parents=True, exist_ok=True)
    with open(PASTA / ".trava", "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Ocupado("outra atualização já está em andamento") from None
        yield    # o kernel solta a trava ao fechar o arquivo, mesmo se o processo morrer


def atualizar(bases: list[Base], forcar: bool = False, agora: float | None = None) -> list[Relatorio]:
    relatorios = []
    with trava():
        for base in bases:
            relatorios.append(_atualizar_uma(base, forcar, agora or time.time()))
    return relatorios


def _atualizar_uma(base: Base, forcar: bool, agora: float) -> Relatorio:
    estado = ler_estado(base)
    if not forcar and estado.tentativa and agora - estado.tentativa < base.intervalo and estado.erro is None:
        return Relatorio(base.nome, "em dia", estado)

    versoes = pasta_da(base) / "versoes"
    versoes.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".baixando-", dir=versoes))
    estado.tentativa = agora
    try:
        versao = base.baixar(tmp, None if forcar else estado.versao)
        if versao is None or (versao == estado.versao and not forcar):
            situacao = "sem novidades"
        else:
            base.validar(tmp)
            final = versoes / time.strftime("%Y%m%d-%H%M%S", time.localtime(agora))
            tmp.rename(final)
            link_tmp = pasta_da(base) / ".atual-novo"
            link_tmp.unlink(missing_ok=True)
            link_tmp.symlink_to(final.relative_to(pasta_da(base)))
            os.replace(link_tmp, pasta_da(base) / "atual")   # a troca, num passo só
            _podar(versoes)
            estado.versao, estado.atualizado = versao, agora
            situacao = "atualizada"
        estado.verificado, estado.erro = agora, None
    except Exception as erro:   # rede, disco, base corrompida: nada disso pode derrubar a Guarnição
        estado.erro = str(erro) or erro.__class__.__name__
        situacao = "erro"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _gravar_estado(base, estado)
    return Relatorio(base.nome, situacao, estado)


def _podar(versoes: Path) -> None:
    for velha in sorted(p for p in versoes.iterdir() if not p.name.startswith("."))[:-VERSOES_GUARDADAS]:
        shutil.rmtree(velha, ignore_errors=True)


def versoes_em_uso(bases: list[Base]) -> str:
    """Entra na versão do motor: base nova que muda vereditos zera o cache."""
    return ",".join(f"{b.nome}={ler_estado(b).versao}" for b in bases if b.invalida_cache)


def baixar_arquivo(url: str, destino: Path, cabecalhos: dict | None = None,
                   limite: int = LIMITE_DOWNLOAD, rotulo: str | None = None) -> str:
    """Baixa por HTTPS com limite de tamanho. Devolve o SHA-256 do que chegou.
    `rotulo` substitui o endereço nas mensagens, quando ele contém uma chave."""
    rotulo = rotulo or url
    if not url.startswith("https://"):
        raise ErroDeBase(f"só baixo por HTTPS: {rotulo}")
    pedido = urllib.request.Request(url, headers={"User-Agent": f"guarnicao/{__version__}", **(cabecalhos or {})})
    h, recebido = hashlib.sha256(), 0
    with urllib.request.urlopen(pedido, timeout=60) as resposta, open(destino, "wb") as f:
        while bloco := resposta.read(1 << 16):
            recebido += len(bloco)
            if recebido > limite:
                raise ErroDeBase(f"download passou de {limite // (1024 * 1024)} MB: {rotulo}")
            f.write(bloco)
            h.update(bloco)
    return h.hexdigest()


def registradas() -> list[Base]:
    """Todas as bases que a Guarnição conhece, na ordem em que são atualizadas."""
    # Aqui dentro: as fontes importam este módulo.
    from .fontes.malwarebazaar import MalwareBazaar
    from .fontes.yara_forge import YaraForge
    return [YaraForge()] + ([MalwareBazaar()] if MalwareBazaar.chave() else [])


def avisos(lista: list[Base] | None = None, agora: float | None = None) -> list[str]:
    """Bases que nunca foram baixadas ou não são conferidas há mais de VELHA_APOS.
    Uma base velha não protege contra o que surgiu depois dela: melhor avisar
    do que mostrar "tudo limpo" com uma base de semanas atrás."""
    saida = []
    if lista is None:
        saida += _aviso_clamav(agora)
    for base in registradas() if lista is None else lista:
        estado = ler_estado(base)
        idade = estado.idade(agora)
        if estado.versao is None:
            saida.append(f"{base.nome}: nunca foi baixada (rode: guarnicao atualizar)")
        elif idade is None or idade > VELHA_APOS:
            dias = int((idade or 0) // 86400)
            motivo = f" ({estado.erro})" if estado.erro else ""
            saida.append(f"{base.nome}: sem atualizar há {dias} dia(s){motivo}")
    return saida


FRESHCLAM = "clamav-freshclam.service"
LIGAR_FRESHCLAM = f"sudo systemctl enable --now {FRESHCLAM.removesuffix('.service')}"
LIGAR_CLAMD = "sudo systemctl enable clamav-daemon && sudo systemctl restart clamav-daemon"


def freshclam_parado() -> bool:
    """O serviço do freshclam existe neste sistema e não está rodando. Parado,
    ele não avisa ninguém: as assinaturas só envelhecem."""
    if not any(Path(pasta, FRESHCLAM).exists()
               for pasta in ("/etc/systemd/system", "/usr/lib/systemd/system", "/lib/systemd/system")):
        return False   # sem o serviço (ex.: freshclam pelo cron): não dá para saber
    try:
        return subprocess.run(["systemctl", "is-active", "--quiet", FRESHCLAM], timeout=5).returncode != 0
    except (OSError, subprocess.SubprocessError):
        return False


def _aviso_clamav(agora: float | None) -> list[str]:
    # As assinaturas do ClamAV não passam por aqui: quem baixa é o freshclam.
    # Mas se ele parar (sem rede, serviço desligado), quem precisa saber é você.
    from . import clamav
    cliente = clamav.conectar()
    if cliente is None:
        # Socket configurado (clamd.conf existe) e ninguém responde: instalado e parado.
        # O systemctl pode até dizer "active" (unit presa em "active (exited)").
        if clamav.encontrar_socket() is not None:
            return [f"clamav: o clamd não responde (para ligar: {LIGAR_CLAMD})"]
        return []
    if freshclam_parado():
        return [f"clamav: o freshclam está parado e as assinaturas não vão mais atualizar ({LIGAR_FRESHCLAM})"]
    try:
        _, _, quando = cliente.versao()
    except OSError:
        return []
    if quando and (agora or time.time()) - quando.timestamp() > VELHA_APOS:
        dias = int(((agora or time.time()) - quando.timestamp()) // 86400)
        return [f"clamav: assinaturas de {dias} dia(s) atrás (o freshclam está rodando?)"]
    return []
