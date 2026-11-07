import os
import stat

from guarnicao import assinaturas, heuristicas, quarentena, scanner

# String de teste EICAR: inofensiva, mas todo antivírus deve detectá-la.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def test_detecta_eicar_por_hash(tmp_path):
    arquivo = tmp_path / "teste.com"
    arquivo.write_bytes(EICAR)
    resultado = scanner.analisar(arquivo, assinaturas.carregar())
    assert resultado.ameaca == "EICAR-Test-File"


def test_arquivo_comum_passa_limpo(tmp_path):
    arquivo = tmp_path / "notas.txt"
    arquivo.write_text("lista de compras: café, pão")
    resultado = scanner.analisar(arquivo, assinaturas.carregar())
    assert not resultado.infectado and not resultado.suspeito


def test_entropia_extremos():
    assert heuristicas.entropia_shannon(b"a" * 1000) == 0.0
    assert heuristicas.entropia_shannon(bytes(range(256)) * 4) == 8.0


def test_sinais_de_elf_disfarcado(tmp_path):
    arquivo = tmp_path / "ferias.jpg"
    arquivo.write_bytes(b"\x7fELF" + os.urandom(2048))
    s = heuristicas.coletar_sinais(arquivo)
    assert s.tipo_real == "ELF" and s.disfarce


def test_extensao_dupla(tmp_path):
    arquivo = tmp_path / "fatura.pdf.sh"
    arquivo.write_text("#!/bin/sh\necho oi\n")
    assert heuristicas.coletar_sinais(arquivo).extensao_dupla


def test_elf_disfarcado_e_suspeito(tmp_path):
    """Depende da sua implementação de avaliar_suspeita()."""
    arquivo = tmp_path / "ferias.jpg"
    arquivo.write_bytes(b"\x7fELF" + os.urandom(2048))
    resultado = scanner.analisar(arquivo, {})
    assert resultado.suspeito
    assert resultado.motivos


def test_quarentena_isola_e_restaura(tmp_path):
    pasta_q = tmp_path / "quarentena"
    arquivo = tmp_path / "malware.sh"
    arquivo.write_text("#!/bin/sh\n")
    arquivo.chmod(0o755)

    id_ = quarentena.isolar(arquivo, "abc", "teste", pasta=pasta_q)
    assert not arquivo.exists()
    bloqueado = pasta_q / f"{id_}.bloqueado"
    assert not bloqueado.stat().st_mode & stat.S_IXUSR
    assert quarentena.listar(pasta_q)[0]["motivo"] == "teste"

    quarentena.restaurar(id_, pasta=pasta_q)
    assert arquivo.exists()
    assert not arquivo.stat().st_mode & stat.S_IXUSR
    assert quarentena.listar(pasta_q) == []


def test_script_em_txt_nao_e_disfarce(tmp_path):
    exemplo = tmp_path / "user-script.txt"
    exemplo.write_text("#!/bin/sh\necho exemplo do manual\n")
    assert not heuristicas.coletar_sinais(exemplo).disfarce
    foto = tmp_path / "foto.jpg"
    foto.write_text("#!/bin/sh\necho nada de foto aqui\n")
    assert heuristicas.coletar_sinais(foto).disfarce
