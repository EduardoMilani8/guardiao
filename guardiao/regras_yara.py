"""Camada YARA: regras que procuram padrões dentro dos arquivos."""

from dataclasses import dataclass
from pathlib import Path

try:
    import yara_x
except ImportError:              # camada opcional: sem yara-x o resto continua funcionando
    yara_x = None

PASTA_PADRAO = Path(__file__).parent.parent / "regras"
PESO_MEDIA = 50                  # pontos de suspeita por regra de gravidade "media"


@dataclass
class Ocorrencia:
    regra: str
    gravidade: str               # "alta" (ameaça) ou "media" (suspeito)
    descricao: str


def disponivel() -> bool:
    return yara_x is not None


def carregar(pasta: Path = PASTA_PADRAO) -> "yara_x.Scanner | None":
    """Compila todos os .yar da pasta. Retorna None se o yara-x não estiver instalado."""
    if yara_x is None:
        return None
    compilador = yara_x.Compiler()
    for arquivo in sorted(pasta.glob("*.yar")):
        compilador.new_namespace(arquivo.stem)
        compilador.add_source(arquivo.read_text(encoding="utf-8"), origin=str(arquivo))
    return yara_x.Scanner(compilador.build())


def verificar(caminho: Path, scanner: "yara_x.Scanner") -> list[Ocorrencia]:
    try:
        resultado = scanner.scan_file(str(caminho))
    except (yara_x.ScanError, yara_x.TimeoutError) as erro:
        raise OSError(f"YARA: {erro}") from erro

    ocorrencias = []
    for regra in resultado.matching_rules:
        meta = dict(regra.metadata)
        ocorrencias.append(Ocorrencia(
            regra=regra.identifier,
            gravidade=meta.get("gravidade", "media"),
            descricao=meta.get("descricao", ""),
        ))
    return ocorrencias
