import io
import tarfile
import time
import zipfile

import pytest

from guarnicao import assinaturas, compactados, regras_yara, scanner

from .test_guarnicao import EICAR
from .test_yara import REVERSE_SHELL


def zip_bytes(membros: dict) -> bytes:
    dados = io.BytesIO()
    with zipfile.ZipFile(dados, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in membros.items():
            z.writestr(nome, conteudo)
    return dados.getvalue()


def tar_gz_bytes(membros: dict) -> bytes:
    dados = io.BytesIO()
    with tarfile.open(fileobj=dados, mode="w:gz") as t:
        for nome, conteudo in membros.items():
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            t.addfile(info, io.BytesIO(conteudo))
    return dados.getvalue()


@pytest.fixture(scope="module")
def banco():
    return assinaturas.carregar()


def analisar(tmp_path, nome, dados, banco, yara=None):
    arquivo = tmp_path / nome
    arquivo.write_bytes(dados)
    return scanner.analisar(arquivo, banco, yara)


def test_eicar_dentro_do_zip(tmp_path, banco):
    r = analisar(tmp_path, "fotos.zip", zip_bytes({"ferias/foto1.jpg": b"jpg", "ferias/setup.com": EICAR}), banco)
    assert r.infectado and r.camada == "hash"
    assert "dentro: ferias/setup.com" in r.ameaca


def test_zip_dentro_de_tar_gz(tmp_path, banco):
    interno = zip_bytes({"leia-me.txt": b"oi", "payload.com": EICAR})
    r = analisar(tmp_path, "backup.tar.gz", tar_gz_bytes({"pasta/arquivos.zip": interno}), banco)
    assert r.infectado and "pasta/arquivos.zip/payload.com" in r.ameaca


def test_extensao_nao_importa_so_o_conteudo(tmp_path, banco):
    # .docx, .jar e .apk são zips por dentro: o cabeçalho PK é o que conta.
    assert analisar(tmp_path, "contrato.docx", zip_bytes({"word/x.bin": EICAR}), banco).infectado


def test_regra_yara_dentro_do_zip(tmp_path, banco):
    pytest.importorskip("yara_x")
    r = analisar(tmp_path, "tema.zip", zip_bytes({"instalar.sh": REVERSE_SHELL}), banco, regras_yara.carregar())
    assert r.infectado and r.camada == "yara" and "instalar.sh" in r.ameaca


def test_zip_bomb_respeita_o_orcamento(tmp_path, banco, monkeypatch):
    monkeypatch.setattr(compactados, "ORCAMENTO", 1024 * 1024)
    # 20 MB de zeros viram uns 20 KB compactados; o EICAR vem depois e não é alcançado.
    bomba = zip_bytes({**{f"zeros{i}.bin": b"\0" * (4 * 1024 * 1024) for i in range(5)}, "z.com": EICAR})
    arquivo = tmp_path / "bomba.zip"
    arquivo.write_bytes(bomba)
    inicio = time.monotonic()
    exame = compactados.examinar(arquivo, banco)
    assert time.monotonic() - inicio < 2
    assert exame.pulados and not exame.ameaca


def test_tar_gz_bomb_para_antes_de_descompactar(tmp_path, banco, monkeypatch):
    monkeypatch.setattr(compactados, "ORCAMENTO", 1024 * 1024)
    arquivo = tmp_path / "bomba.tar.gz"
    arquivo.write_bytes(tar_gz_bytes({"zeros.bin": b"\0" * (8 * 1024 * 1024), "z.com": EICAR}))
    exame = compactados.examinar(arquivo, banco)
    assert exame.pulados == ["zeros.bin (limite do pacote)"]


def test_membro_cifrado_e_pulado(tmp_path, banco):
    # O zipfile do Python não grava cifrado; ligamos o bit "cifrado" direto nos
    # bytes, no cabeçalho local e no diretório central (como num zip com senha).
    dados = bytearray(zip_bytes({"segredo.exe": b"conteudo"}))
    for assinatura, deslocamento in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        dados[dados.index(assinatura) + deslocamento] |= 0x1
    arquivo = tmp_path / "amostra.zip"
    arquivo.write_bytes(bytes(dados))
    assert compactados.examinar(arquivo, banco).pulados == ["segredo.exe (cifrado)"]


def test_nada_e_extraido_para_o_disco(tmp_path, banco):
    pasta = tmp_path / "p"
    pasta.mkdir()
    analisar(pasta, "truque.zip", zip_bytes({"../../fora.txt": b"x", "/etc/escapou": b"y"}), banco)
    assert sorted(p.name for p in tmp_path.rglob("*")) == ["p", "truque.zip"]


def test_link_no_tar_e_ignorado(tmp_path, banco):
    dados = io.BytesIO()
    with tarfile.open(fileobj=dados, mode="w") as t:
        link = tarfile.TarInfo("senhas")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/shadow"
        t.addfile(link)
    arquivo = tmp_path / "x.tar"
    arquivo.write_bytes(dados.getvalue())
    assert compactados.examinar(arquivo, banco).membros == 0


def test_limite_de_profundidade(tmp_path, banco, monkeypatch):
    monkeypatch.setattr(compactados, "MAX_PROFUNDIDADE", 2)
    pacote = EICAR
    for i in range(3):   # EICAR dentro de 3 zips aninhados
        pacote = zip_bytes({f"nivel{i}": pacote})
    assert not analisar(tmp_path, "matrioska.zip", pacote, banco).infectado


@pytest.mark.parametrize("dados", [b"PK\x03\x04 isto nao e um zip", b"\x1f\x8b gzip quebrado", b"texto comum"])
def test_pacote_corrompido_ou_texto_nao_quebra(tmp_path, banco, dados):
    assert not analisar(tmp_path, "x.bin", dados, banco).infectado


def test_regras_yara_dentro_de_um_wheel_nao_sao_ameaca(tmp_path, banco):
    pytest.importorskip("yara_x")
    from .test_yara import REGRA_DE_OUTRA_FERRAMENTA
    wheel = zip_bytes({"skillspector/yara_rules/cryptominers.yar": REGRA_DE_OUTRA_FERRAMENTA})
    r = analisar(tmp_path, "skillspector-2.12.0-py3-none-any.whl", wheel, banco, regras_yara.carregar())
    assert not r.infectado and not r.suspeito
