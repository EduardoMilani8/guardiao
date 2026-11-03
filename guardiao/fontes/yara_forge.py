"""YARA Forge: milhares de regras YARA da comunidade, já testadas e pontuadas.

https://github.com/YARAHQ/yara-forge — publica um pacote novo quase todo dia.
Usamos o pacote "core", o de menos falsos positivos. Cada regra traz um
`score` de 0 a 100: a partir de 80 indica malware; abaixo, algo suspeito.
As regras têm licenças variadas (algumas não comerciais): são baixadas para
uso local, nunca redistribuídas com o Guardião.
"""

import json
import zipfile
from pathlib import Path

from .. import regras_yara
from ..bases import Base, ErroDeBase, baixar_arquivo

API = "https://api.github.com/repos/YARAHQ/yara-forge/releases/latest"
PACOTE = "yara-forge-rules-core.zip"
MEMBRO = "packages/core/yara-rules-core.yar"
LIMITE_REGRAS = 64 * 1024 * 1024
MINIMO_DE_REGRAS = 1000   # pacote bem menor que isso veio truncado ou errado


class YaraForge(Base):
    nome = "yara-forge"
    descricao = "regras YARA da comunidade (YARA Forge, pacote core)"
    intervalo = 24 * 3600

    def baixar(self, destino: Path, versao_atual: str | None) -> str | None:
        baixar_arquivo(API, destino / "release.json", {"Accept": "application/vnd.github+json"}, limite=1 << 20)
        release = json.loads((destino / "release.json").read_text())
        versao = release["tag_name"]
        if versao == versao_atual:
            return None
        asset = next((a for a in release["assets"] if a["name"] == PACOTE), None)
        if asset is None:
            raise ErroDeBase(f"release {versao} sem {PACOTE}")
        sha = baixar_arquivo(asset["browser_download_url"], destino / PACOTE)
        esperado = (asset.get("digest") or "").removeprefix("sha256:")
        if esperado and sha != esperado:
            raise ErroDeBase(f"{PACOTE} chegou diferente do publicado (sha256 {sha[:12]}…)")
        _extrair(destino / PACOTE, destino / "regras.yar")
        (destino / PACOTE).unlink()
        (destino / "release.json").unlink()
        return versao

    def validar(self, pasta: Path) -> None:
        quantas = regras_yara.validar_fonte(pasta / "regras.yar")
        if quantas < MINIMO_DE_REGRAS:
            raise ErroDeBase(f"só {quantas} regras: pacote incompleto")


def _extrair(pacote: Path, destino: Path) -> None:
    # Só o arquivo esperado, com limite de tamanho: nada de extrair caminhos
    # arbitrários que viessem dentro do zip (ex.: ../../.bashrc).
    with zipfile.ZipFile(pacote) as z:
        try:
            info = z.getinfo(MEMBRO)
        except KeyError:
            raise ErroDeBase(f"{MEMBRO} não está no pacote") from None
        if info.file_size > LIMITE_REGRAS:
            raise ErroDeBase("arquivo de regras grande demais")
        with z.open(info) as origem, open(destino, "wb") as saida:
            saida.write(origem.read(LIMITE_REGRAS + 1)[:LIMITE_REGRAS])
