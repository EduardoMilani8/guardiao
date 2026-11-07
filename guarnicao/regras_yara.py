"""Camada YARA: regras que procuram padrões dentro dos arquivos.

Junta as nossas regras (regras/*.yar) com as das bases baixadas (ex.: YARA
Forge), cada conjunto no próprio namespace para nomes iguais não colidirem.
"""

import re
from dataclasses import dataclass
from pathlib import Path

try:
    import yara_x
except ImportError:              # camada opcional: sem yara-x o resto continua funcionando
    yara_x = None

PASTA_PADRAO = Path(__file__).parent.parent / "regras"
PASTA_DEV = PASTA_PADRAO / "dev"  # só para o módulo de dev (não entra em carregar() padrão)
PESO_MEDIA = 50                  # pontos de suspeita por regra de gravidade "media"
DESLIGADAS = PASTA_PADRAO / "desligadas.txt"   # regras das bases que deram falso positivo aqui
NOME_NAS_BASES = "regras.yar"
TEMPO_MAXIMO = 30                # segundos por arquivo: nenhum arquivo trava a varredura


@dataclass
class Ocorrencia:
    regra: str
    gravidade: str               # "alta" (ameaça) ou "media" (suspeito)
    descricao: str


def disponivel() -> bool:
    return yara_x is not None


def regras_das_bases() -> list[Path]:
    from . import bases   # aqui dentro: as fontes importam este módulo
    fontes = []
    for base in bases.registradas():
        pasta = bases.atual(base)
        if pasta and (pasta / NOME_NAS_BASES).is_file():
            fontes.append(pasta / NOME_NAS_BASES)
    return fontes


def carregar(pasta: Path = PASTA_PADRAO, com_bases: bool | None = None) -> "yara_x.Scanner | None":
    """Compila os .yar da pasta (e, na pasta padrão, os das bases baixadas).
    Retorna None se o yara-x não estiver instalado.

    Se este processo nasceu do forkserver de contexto(), as regras já vêm
    compiladas e divididas com os outros processos: só cria o Scanner."""
    if yara_x is None:
        return None
    usa_bases = pasta == PASTA_PADRAO if com_bases is None else com_bases
    extras = regras_das_bases() if usa_bases else []
    if pasta == PASTA_PADRAO and usa_bases and _compartilhadas and _compartilhadas[0] == extras:
        regras = _compartilhadas[1]
    else:
        regras = _compilar_com_reserva(pasta, extras)
    scanner = yara_x.Scanner(regras)
    scanner.set_timeout(TEMPO_MAXIMO)
    return scanner


def _compilar_com_reserva(pasta: Path, extras: list[Path]):
    try:
        return _compilar(pasta, extras)
    except yara_x.CompileError:
        return _compilar(pasta, [])   # base estragada: seguimos ao menos com as nossas


# --- regras divididas entre processos ------------------------------------------
#
# Cada processo que analisa precisa das regras compiladas (uns 170 MB com o YARA
# Forge). Compiladas uma vez no forkserver, os filhos nascem com elas e o Linux
# divide as páginas (copy-on-write): as regras só são lidas, nunca copiadas.
# 4 processos da varredura: de ~670 MB para ~240 MB, medido em 07/11/2026.

_compartilhadas: "tuple[list[Path], yara_x.Rules] | None" = None
_fontes_no_servidor: list[Path] | None = None   # com que fontes o forkserver atual compilou


def preparar_compartilhadas() -> None:
    """Compila as regras padrão e guarda para os processos que nascerem daqui."""
    global _compartilhadas
    if yara_x is None:
        return
    extras = regras_das_bases()
    _compartilhadas = (extras, _compilar_com_reserva(PASTA_PADRAO, extras))


def base_mudou() -> bool:
    """As bases mudaram depois que o forkserver compilou as regras dele?"""
    return _fontes_no_servidor is not None and _fontes_no_servidor != regras_das_bases()


def contexto():
    """O contexto de multiprocessing para os processos que analisam.

    forkserver, e não fork: copiar um processo com threads (o launcher, o
    protetor) pode travar. O forkserver tem uma thread só e carrega as regras
    uma vez. Se as bases mudaram, encerra o forkserver velho para o próximo
    grupo de processos nascer com as regras novas."""
    import multiprocessing
    from multiprocessing import forkserver
    global _fontes_no_servidor
    servidor = forkserver._forkserver
    if base_mudou() and (parar := getattr(servidor, "_stop", None)):
        parar()   # API interna; sem ela, cada processo recompila sozinho (funciona, só gasta mais)
    if getattr(servidor, "_forkserver_pid", None) is None:
        servidor.set_forkserver_preload(["guarnicao.regras_compartilhadas"])
        _fontes_no_servidor = regras_das_bases()
    return multiprocessing.get_context("forkserver")


def _compilar(pasta: Path, extras: list[Path]):
    compilador = yara_x.Compiler()
    for arquivo in sorted(pasta.glob("*.yar")):
        compilador.new_namespace(arquivo.stem)
        compilador.add_source(arquivo.read_text(encoding="utf-8"), origin=str(arquivo))
    for arquivo in extras:
        compilador.new_namespace("base_" + arquivo.parent.parent.parent.name.replace("-", "_"))
        compilador.add_source(arquivo.read_text(encoding="utf-8", errors="replace"), origin=str(arquivo))
    return compilador.build()


def validar_fonte(arquivo: Path) -> int:
    """Confere se um arquivo de regras baixado compila. Devolve quantas regras tem."""
    if yara_x is None:
        raise RuntimeError("yara-x não instalado: não dá para validar regras")
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    yara_x.compile(texto)   # levanta CompileError se estiver quebrado
    return len(re.findall(r"^\s*(?:private\s+|global\s+)*rule\s", texto, re.MULTILINE))


def _desligadas() -> set[str]:
    global _cache_desligadas
    if _cache_desligadas is None:
        try:
            linhas = DESLIGADAS.read_text(encoding="utf-8").splitlines()
        except OSError:
            linhas = []
        _cache_desligadas = {l.split("#")[0].strip() for l in linhas} - {""}
    return _cache_desligadas


_cache_desligadas: set[str] | None = None


def _gravidade(meta: dict) -> str:
    if "gravidade" in meta:
        return meta["gravidade"]
    # Regras da comunidade (YARA Forge) usam `score`: 80+ é malware.
    score = meta.get("score")
    if isinstance(score, int):
        return "alta" if score >= 80 else "media" if score >= 60 else "info"
    return "media"


def verificar(caminho: Path, scanner: "yara_x.Scanner") -> list[Ocorrencia]:
    try:
        resultado = scanner.scan_file(str(caminho))
    except (yara_x.ScanError, yara_x.TimeoutError) as erro:
        raise OSError(f"YARA: {erro}") from erro
    return _ocorrencias(resultado)


def verificar_bytes(dados: bytes, scanner: "yara_x.Scanner") -> list[Ocorrencia]:
    """Aplica as regras a um conteúdo em memória, ex.: um membro de um .zip."""
    try:
        return _ocorrencias(scanner.scan(dados))
    except (yara_x.ScanError, yara_x.TimeoutError) as erro:
        raise OSError(f"YARA: {erro}") from erro


def verificar_texto(texto: str, scanner: "yara_x.Scanner") -> list[Ocorrencia]:
    """Aplica as regras a um trecho de texto, ex.: o comando de um script npm."""
    return _ocorrencias(scanner.scan(texto.encode("utf-8", errors="replace")))


def _ocorrencias(resultado) -> list[Ocorrencia]:
    ocorrencias = []
    for regra in resultado.matching_rules:
        if regra.identifier in _desligadas():
            continue
        meta = dict(regra.metadata)
        ocorrencias.append(Ocorrencia(
            regra=regra.identifier,
            gravidade=_gravidade(meta),
            descricao=meta.get("descricao") or meta.get("description", ""),
        ))
    return ocorrencias
