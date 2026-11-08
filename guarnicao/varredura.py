"""Varreduras rápida, completa e personalizada.

Decide o que percorrer (raízes e exclusões), pula o que está no cache e
distribui a análise entre vários processos. Gera, em ordem:
`Progresso` (de tempos em tempos), `Resultado` / `(caminho, erro)` por arquivo
analisado e um `Resumo` no final.
"""

import fnmatch
import os
import re
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from . import andamento, assinaturas, bases, clamav, quarentena, regras_yara, scanner
from .cache import Cache
from .caminhos import CONFIG, casa_real

# Lista de PERMITIDOS: sistemas de arquivos que guardam arquivos de verdade.
# proc, sysfs, devtmpfs etc. são janelas para o kernel (ler /dev/zero nunca
# termina); squashfs são snaps somente leitura; fuse.* e nfs/cifs são de rede.
FS_LOCAIS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "zfs", "jfs", "vfat",
             "exfat", "ntfs", "ntfs3", "fuseblk", "tmpfs"}
EXTERNOS = ("/media", "/run/media", "/mnt")
INTERVALO_PROGRESSO = 0.25   # segundos (painel)
INTERVALO_ANDAMENTO = 1.0    # segundos (escudo da barra)
LOTE = 2000                  # arquivos analisados por vez (o resto do disco não fica na memória)


@dataclass
class Exclusoes:
    pastas: list[str] = field(default_factory=list)     # caminhos absolutos
    padroes: list[str] = field(default_factory=list)    # padrões de nome, ex.: "*.iso"
    tamanho_max: int = 256 * 1024 * 1024

    def ignora_pasta(self, caminho: str) -> bool:
        return any(caminho == p or caminho.startswith(p + os.sep) for p in self.pastas)

    def ignora_nome(self, nome: str) -> bool:
        return any(fnmatch.fnmatch(nome, p) for p in self.padroes)


@dataclass
class Progresso:
    fase: str            # "listando" ou "analisando"
    vistos: int
    total: int
    atual: str


@dataclass
class Resumo:
    analisados: int = 0
    em_cache: int = 0
    ameacas: int = 0
    suspeitos: int = 0
    sem_permissao: int = 0
    grandes: int = 0
    segundos: float = 0.0


# --- configuração e raízes ---------------------------------------------------------

def carregar_exclusoes(config: Path = CONFIG) -> Exclusoes:
    """Exclusões padrão + as do ~/.config/guarnicao/config.toml, se existir.

    Exemplo de config.toml:
        excluir_pastas = ["~/Vídeos", "~/VirtualBox VMs"]
        excluir_padroes = ["*.iso"]
        tamanho_maximo_mb = 512
    """
    exclusoes = Exclusoes(pastas=[
        str(quarentena.PASTA_PADRAO),             # senão as ameaças isoladas seriam achadas de novo
        str(casa_real() / ".local" / "share" / "guarnicao" / "quarentena"),   # a do usuário, se via sudo
        str(regras_yara.PASTA_PADRAO.resolve()),  # as regras contêm os padrões que procuram
        str(bases.PASTA),                         # idem para as regras e hashes baixados
        str(Path(__file__).parent.parent / ".venv"),
    ])
    if config.is_file():
        dados = tomllib.loads(config.read_text(encoding="utf-8"))
        exclusoes.pastas += [str(Path(p).expanduser().resolve()) for p in dados.get("excluir_pastas", [])]
        exclusoes.padroes += list(dados.get("excluir_padroes", []))
        if "tamanho_maximo_mb" in dados:
            exclusoes.tamanho_max = int(dados["tamanho_maximo_mb"]) * 1024 * 1024
    return exclusoes


def _desescapar(campo: str) -> str:
    # /proc/self/mounts escreve espaços e afins em octal: "Meu\040Disco"
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), campo)


def raizes_completa(incluir_externos: bool = False, mounts: str | None = None) -> list[Path]:
    """Pontos de montagem com arquivos de verdade, do disco inteiro."""
    if mounts is None:
        mounts = Path("/proc/self/mounts").read_text()
    raizes = []
    for linha in mounts.splitlines():
        partes = linha.split()
        if len(partes) < 3:
            continue
        ponto, tipo = _desescapar(partes[1]), partes[2]
        if tipo not in FS_LOCAIS:
            continue
        if not incluir_externos and any(ponto == e or ponto.startswith(e + "/") for e in EXTERNOS):
            continue
        raizes.append(Path(ponto))
    return sorted(set(raizes))


def _pasta_xdg(chave: str, padrao: str) -> Path:
    casa = casa_real()
    arquivo = casa / ".config" / "user-dirs.dirs"
    try:
        if m := re.search(rf'^XDG_{chave}_DIR="(.+)"', arquivo.read_text(), re.MULTILINE):
            return Path(m.group(1).replace("$HOME", str(casa)))
    except OSError:
        pass
    return casa / padrao


def raizes_rapida() -> list[Path]:
    """Onde malware costuma chegar ou se instalar para rodar sozinho."""
    casa = casa_real()
    candidatas = [
        _pasta_xdg("DOWNLOAD", "Downloads"), _pasta_xdg("DESKTOP", "Desktop"),
        Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"),
        casa / ".local" / "bin", casa / "bin",
        casa / ".config" / "autostart", casa / ".config" / "systemd" / "user",
        casa / ".local" / "share" / "applications",
        Path("/etc/systemd/system"), Path("/etc/cron.d"), Path("/etc/cron.daily"),
        Path("/etc/cron.hourly"), Path("/var/spool/cron"),
    ]
    return sem_aninhadas([p for p in candidatas if p.is_dir()])


def sem_aninhadas(raizes: list[Path]) -> list[Path]:
    """Remove raízes que estão dentro de outra (senão seriam varridas duas vezes)."""
    resolvidas = sorted({p.resolve() for p in raizes})
    return [p for p in resolvidas if not any(p != q and p.is_relative_to(q) for q in resolvidas)]


# --- percorrer ---------------------------------------------------------------------

def percorrer(raiz: Path, exclusoes: Exclusoes, resumo: Resumo) -> Iterator[tuple[str, os.stat_result]]:
    """Arquivos regulares sob `raiz`, sem seguir links e sem trocar de sistema de arquivos.

    Ao chegar num ponto de montagem (ex.: /dev/shm dentro de /dev), para: cada
    sistema de arquivos permitido é percorrido como uma raiz própria.
    """
    try:
        st_raiz = raiz.stat()
    except OSError:
        resumo.sem_permissao += 1
        return
    if raiz.is_file():
        yield str(raiz), st_raiz
        return
    dispositivo = st_raiz.st_dev
    pilha = [str(raiz)]
    while pilha:
        pasta = pilha.pop()
        if exclusoes.ignora_pasta(pasta):
            continue
        try:
            entradas = os.scandir(pasta)
        except OSError:
            resumo.sem_permissao += 1
            continue
        with entradas:
            for e in entradas:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.stat(follow_symlinks=False).st_dev == dispositivo:
                            pilha.append(e.path)
                    elif e.is_file(follow_symlinks=False) and not exclusoes.ignora_nome(e.name):
                        st = e.stat(follow_symlinks=False)
                        if st.st_size > exclusoes.tamanho_max:
                            resumo.grandes += 1
                        else:
                            yield e.path, st
                except OSError:
                    resumo.sem_permissao += 1


# --- análise em paralelo -------------------------------------------------------------

_banco: scanner.BancoDeHashes = {}
_yara = None
_clamav = None


def _iniciar_processo() -> None:
    # Cada processo tem o próprio banco e o próprio Scanner do YARA-X; as regras
    # compiladas por baixo do Scanner vêm do forkserver, divididas entre todos.
    global _banco, _yara, _clamav
    _banco = assinaturas.carregar()
    _yara = regras_yara.carregar()
    _clamav = clamav.conectar()


def _analisar(caminho: str):
    try:
        return scanner.analisar(Path(caminho), _banco, _yara, _clamav)
    except OSError as erro:
        return Path(caminho), erro


def executar(
    raizes: list[Path],
    exclusoes: Exclusoes | None = None,
    usar_cache: bool = True,
    processos: int | None = None,
    cache: Cache | None = None,
    rotulo: str | None = None,
) -> Iterator[Progresso | scanner.Resultado | tuple[Path, OSError] | Resumo]:
    """Varre as raízes. Com `rotulo` (ex.: "rápida"), grava o andamento para o
    escudo da barra e apaga no fim, inclusive se a varredura for interrompida."""
    gravado = None
    try:
        for item in _executar(raizes, exclusoes, usar_cache, processos, cache):
            # No máximo uma vez por segundo: cada gravação acorda o escudo da barra.
            if rotulo and isinstance(item, Progresso) and (
                    gravado is None or time.monotonic() - gravado >= INTERVALO_ANDAMENTO):
                gravado = time.monotonic()
                andamento.gravar(rotulo, item.vistos, item.total)
            yield item
    finally:
        if rotulo:
            andamento.apagar()


def _executar(
    raizes: list[Path],
    exclusoes: Exclusoes | None = None,
    usar_cache: bool = True,
    processos: int | None = None,
    cache: Cache | None = None,
) -> Iterator[Progresso | scanner.Resultado | tuple[Path, OSError] | Resumo]:
    inicio = time.monotonic()
    exclusoes = exclusoes or carregar_exclusoes()
    processos = processos or os.cpu_count() or 1
    resumo = Resumo()
    cache_proprio = usar_cache and cache is None
    if cache_proprio:
        cache = Cache()
    ultimo = 0.0
    banco = assinaturas.carregar()   # para reconferir os hashes guardados no cache

    try:
        # 1) Contar, só para a barra de andamento saber o total. Não guarda nada:
        #    guardar o disco inteiro (1,1 milhão de caminhos com stat) custava ~800 MB.
        total = 0
        for raiz in raizes:
            for caminho, _ in percorrer(raiz, exclusoes, Resumo()):
                total += 1
                if time.monotonic() - ultimo > INTERVALO_PROGRESSO:
                    ultimo = time.monotonic()
                    yield Progresso("listando", total, 0, caminho)

        # 2) Andar de novo e analisar em lotes: na memória, só um lote por vez.
        yield Progresso("analisando", 0, total, "")

        def lotes():
            lote: dict[str, os.stat_result] = {}
            for raiz in raizes:
                for caminho, st in percorrer(raiz, exclusoes, resumo):
                    sha = cache.consultar(st) if cache is not None else None
                    # Limpo da última vez, mas o hash pode ter virado ameaça numa base nova.
                    if sha is not None and banco.get(sha) is None:
                        resumo.em_cache += 1
                    else:
                        lote[caminho] = st
                        if len(lote) >= LOTE:
                            yield lote
                            lote = {}
            if lote:
                yield lote

        for lote, item in _mapear(lotes(), processos, total):
            if isinstance(item, tuple):
                resumo.sem_permissao += 1
                yield item
                continue
            resumo.analisados += 1
            st = lote[str(item.caminho)]
            if item.infectado:
                resumo.ameacas += 1
            elif item.suspeito:
                resumo.suspeitos += 1
            if cache is not None:
                if item.infectado or item.suspeito:
                    cache.esquecer(st)
                else:
                    cache.marcar_limpo(st, item.sha256)
            yield item
            if time.monotonic() - ultimo > INTERVALO_PROGRESSO:
                ultimo = time.monotonic()
                yield Progresso("analisando", resumo.em_cache + resumo.analisados, total, str(item.caminho))
        # Varreduras curtas acabam antes do primeiro intervalo. Conta só o que foi
        # verificado: quem falhou na leitura (sumiu, sem permissão) não entra.
        yield Progresso("analisando", resumo.em_cache + resumo.analisados, total, "")
    finally:
        if cache is not None:
            cache.fechar() if cache_proprio else cache.salvar()

    resumo.segundos = time.monotonic() - inicio
    yield resumo


def _mapear(lotes, processos: int, total: int):
    """(lote, resultado) de cada arquivo, um lote por vez."""
    if processos <= 1 or total < 50:
        # Poucos arquivos: abrir processos custa mais que ganha. Banco e Scanner
        # ficam locais, porque o Scanner do YARA-X não pode trocar de thread.
        banco, yara, cliente = assinaturas.carregar(), regras_yara.carregar(), clamav.conectar()
        for lote in lotes:
            for caminho in lote:
                try:
                    yield lote, scanner.analisar(Path(caminho), banco, yara, cliente)
                except OSError as erro:
                    yield lote, (Path(caminho), erro)
        return
    # Os processos nascem do forkserver já com as regras YARA, divididas na memória.
    with regras_yara.contexto().Pool(processos, initializer=_iniciar_processo) as pool:
        # Se quem consome parar no meio (ex.: a página do launcher foi fechada),
        # o `with` encerra os processos.
        for lote in lotes:
            for item in pool.imap_unordered(_analisar, list(lote), chunksize=16):
                yield lote, item
