"""Módulo de dev: riscos na cadeia de pacotes e em projetos clonados.

Procura código que roda sozinho (scripts de instalação npm, setup.py, hooks
do git, tarefas automáticas do VS Code) e dependências com nome parecido
com pacotes populares (typosquatting).
"""

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from . import regras_yara

PASTA_DADOS = Path(__file__).parent.parent / "dados"
IGNORAR = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}
SCRIPTS_INSTALACAO = ("preinstall", "install", "postinstall")
SCRIPTS_RAIZ = SCRIPTS_INSTALACAO + ("prepare",)   # prepare só roda no próprio projeto
ARQUIVO_CITADO = re.compile(r"[\w./@-]+\.(?:c?js|mjs|sh|py)\b")
TAMANHO_MAX = 2 * 1024 * 1024
ORDEM = {"alta": 0, "media": 1, "info": 2}


@dataclass
class Achado:
    gravidade: str        # "alta", "media" ou "info"
    categoria: str        # ex.: "script de instalação", "typosquatting"
    arquivo: Path
    mensagem: str


def auditar(raiz: Path) -> list[Achado]:
    achados = Auditor(raiz).auditar()
    return sorted(achados, key=lambda a: (ORDEM.get(a.gravidade, 9), str(a.arquivo)))


class Auditor:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        # Regras gerais (shell reverso, minerador...) + regras específicas de dev.
        self.scanners = [s for s in (regras_yara.carregar(), regras_yara.carregar(regras_yara.PASTA_DEV)) if s]

    def auditar(self) -> list[Achado]:
        return [
            *self._scripts_npm(),
            *self._typosquatting(),
            *self._vscode(),
            *self._hooks_git(),
            *self._setup_py(),
        ]

    # --- análise de código --------------------------------------------------

    def _analisar(self, texto: str, arquivo: Path, categoria: str, contexto: str) -> list[Achado]:
        achados, vistas = [], set()
        for scanner in self.scanners:
            for o in regras_yara.verificar_texto(texto, scanner):
                if o.regra not in vistas:
                    vistas.add(o.regra)
                    achados.append(Achado(o.gravidade, categoria, arquivo, f"{contexto}: {o.descricao}"))
        return achados

    def _ler(self, caminho: Path) -> str | None:
        try:
            if caminho.is_file() and caminho.stat().st_size <= TAMANHO_MAX:
                return caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        return None

    # --- scripts de instalação do npm ---------------------------------------

    def _scripts_npm(self) -> Iterator[Achado]:
        for pacote_json in _package_jsons(self.raiz):
            try:
                dados = json.loads(pacote_json.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            scripts = dados.get("scripts") if isinstance(dados, dict) else None
            if not isinstance(scripts, dict):
                continue

            dependencia = "node_modules" in pacote_json.parts
            nome = dados.get("name") or pacote_json.parent.name
            for gatilho in SCRIPTS_INSTALACAO if dependencia else SCRIPTS_RAIZ:
                comando = scripts.get(gatilho)
                if not isinstance(comando, str):
                    continue
                contexto = f"{nome} roda '{gatilho}'"
                achados = self._analisar(comando, pacote_json, "script de instalação", contexto)

                # O código malicioso costuma estar no arquivo chamado pelo comando
                # ("node instalar.js"), não no comando em si.
                for citado in ARQUIVO_CITADO.findall(comando):
                    caminho = pacote_json.parent / citado
                    if (texto := self._ler(caminho)) is not None:
                        achados += self._analisar(texto, caminho, "script de instalação", f"{contexto} → {citado}")

                if achados:
                    yield from achados
                elif dependencia:
                    yield Achado("info", "script de instalação", pacote_json, f"{contexto}: {comando}")

    # --- typosquatting -------------------------------------------------------

    def _typosquatting(self) -> Iterator[Achado]:
        npm = _carregar_lista("populares_npm.txt", _normalizar_npm)
        pypi = _carregar_lista("populares_pypi.txt", _normalizar_pypi)

        for arquivo in _arquivos(self.raiz, lambda n: n == "package.json"):
            for nome in _deps_npm(arquivo):
                if alvo := parecido(_normalizar_npm(nome), npm):
                    yield _achado_typo(arquivo, nome, alvo)

        for arquivo in _arquivos(self.raiz, _eh_arquivo_de_deps_python):
            for nome in _deps_python(arquivo):
                if alvo := parecido(_normalizar_pypi(nome), pypi):
                    yield _achado_typo(arquivo, nome, alvo)

    # --- execução automática ao abrir o projeto ------------------------------

    def _vscode(self) -> Iterator[Achado]:
        for tasks in _arquivos(self.raiz, lambda n: n == "tasks.json"):
            if tasks.parent.name != ".vscode" or (texto := self._ler(tasks)) is None:
                continue
            if re.search(r'"runOn"\s*:\s*"folderOpen"', texto):
                yield Achado("media", "auto-execução", tasks,
                             "tarefa do VS Code roda sozinha ao abrir a pasta (runOn: folderOpen); "
                             "confira o comando antes de confiar no workspace")
            yield from self._analisar(texto, tasks, "auto-execução", "tarefa do VS Code")

    def _hooks_git(self) -> Iterator[Achado]:
        pastas = [self.raiz / ".git" / "hooks", self.raiz / ".husky"]
        if (caminho_custom := _hooks_path(self.raiz)) is not None:
            pastas.append(caminho_custom)

        for pasta in pastas:
            if not pasta.is_dir():
                continue
            for hook in sorted(pasta.iterdir()):
                if hook.suffix == ".sample" or not hook.is_file() or (texto := self._ler(hook)) is None:
                    continue
                achados = self._analisar(texto, hook, "hook do git", f"hook '{hook.name}'")
                if achados:
                    yield from achados
                elif os.access(hook, os.X_OK):
                    yield Achado("info", "hook do git", hook, f"hook '{hook.name}' ativo")

    # --- setup.py ------------------------------------------------------------

    def _setup_py(self) -> Iterator[Achado]:
        for setup in _arquivos(self.raiz, lambda n: n == "setup.py"):
            if (texto := self._ler(setup)) is not None:
                yield from self._analisar(texto, setup, "setup.py", "roda em 'pip install'")


# --- typosquatting: comparação de nomes ---------------------------------------

def distancia(a: str, b: str) -> int:
    """Distância de Damerau-Levenshtein (versão OSA): inserção, remoção,
    troca de letra e inversão de duas letras vizinhas contam 1 cada."""
    anterior2, anterior = [], list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            custo = 0 if ca == cb else 1
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + custo))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                atual[j] = min(atual[j], anterior2[j - 2] + 1)
        anterior2, anterior = anterior, atual
    return anterior[-1]


def parecido(nome: str, populares: set[str]) -> str | None:
    """Pacote popular de que `nome` é uma possível imitação, ou None."""
    if nome in populares or len(nome) < 5:   # nomes curtos geram falso positivo demais
        return None
    limite = 2 if len(nome) >= 10 else 1
    for popular in populares:
        if abs(len(popular) - len(nome)) <= limite and distancia(nome, popular) <= limite:
            return popular
    return None


def _achado_typo(arquivo: Path, nome: str, alvo: str) -> Achado:
    return Achado("media", "typosquatting", arquivo,
                  f"dependência '{nome}' é parecida com '{alvo}': confira se não é um pacote impostor")


def _normalizar_npm(nome: str) -> str:
    return nome.strip().lower()


def _normalizar_pypi(nome: str) -> str:
    return re.sub(r"[-_.]+", "-", nome.strip().lower())   # PEP 503


def _carregar_lista(nome: str, normalizar) -> set[str]:
    linhas = (PASTA_DADOS / nome).read_text(encoding="utf-8").splitlines()
    return {normalizar(l) for l in linhas if l.strip() and not l.startswith("#")}


def _deps_npm(package_json: Path) -> list[str]:
    try:
        dados = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    nomes = []
    for campo in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        if isinstance(dados.get(campo), dict):
            nomes += dados[campo]
    return nomes


def _eh_arquivo_de_deps_python(nome: str) -> bool:
    return nome == "pyproject.toml" or (nome.startswith("requirements") and nome.endswith(".txt"))


def _deps_python(arquivo: Path) -> list[str]:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except OSError:
        return []
    if arquivo.name != "pyproject.toml":
        return [m.group(0) for l in texto.splitlines()
                if (m := re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", l.strip()))]
    try:
        dados = tomllib.loads(texto)
    except tomllib.TOMLDecodeError:
        return []
    projeto = dados.get("project", {})
    especificacoes = list(projeto.get("dependencies", []))
    for grupo in projeto.get("optional-dependencies", {}).values():
        especificacoes += grupo
    nomes = [m.group(0) for e in especificacoes if (m := re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", e))]
    nomes += [n for n in dados.get("tool", {}).get("poetry", {}).get("dependencies", {}) if n != "python"]
    return nomes


# --- percorrer o projeto -------------------------------------------------------

def _arquivos(raiz: Path, filtro) -> Iterator[Path]:
    """Arquivos do próprio projeto (fora de node_modules, .venv, .git...)."""
    for pasta, subpastas, nomes in os.walk(raiz):
        subpastas[:] = [s for s in subpastas if s not in IGNORAR]
        for nome in nomes:
            if filtro(nome):
                yield Path(pasta) / nome


def _package_jsons(raiz: Path) -> Iterator[Path]:
    """package.json do projeto e de cada pacote instalado em node_modules.

    Dentro de node_modules só vale o package.json da raiz de cada pacote
    (node_modules/x ou node_modules/@escopo/x); os de exemplos e testes
    internos dos pacotes nunca são executados pelo npm.
    """
    for pasta, subpastas, nomes in os.walk(raiz):
        subpastas[:] = [s for s in subpastas if s not in IGNORAR - {"node_modules"}]
        if "package.json" not in nomes:
            continue
        p = Path(pasta)
        if "node_modules" not in p.parts:
            yield p / "package.json"
        elif p.parent.name == "node_modules" or (p.parent.name.startswith("@") and p.parent.parent.name == "node_modules"):
            yield p / "package.json"


def _hooks_path(raiz: Path) -> Path | None:
    """core.hooksPath do .git/config, se configurado (ex.: husky)."""
    config = raiz / ".git" / "config"
    try:
        if m := re.search(r"^\s*hooksPath\s*=\s*(.+)$", config.read_text(), re.MULTILINE):
            caminho = Path(m.group(1).strip()).expanduser()
            return caminho if caminho.is_absolute() else raiz / caminho
    except OSError:
        pass
    return None
