# Extensão do GNOME (escudo e avisos na muralha) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um escudo na barra do GNOME que mostra o estado da Guarnição e avisos com a arte da muralha, sem quebrar nada para quem não tem a extensão.

**Architecture:** Os avisos continuam indo pelo `notify-send`, agora com dados escondidos (hints `x-guarnicao-*`). A extensão (GNOME Shell 50, JavaScript ESM) guarda esses dados ao envolver `NotifyAsync` do daemon de notificações e troca o recheio do balão em `MessageTray._showNotification`. O escudo lê `guarnicao estado --json` e o arquivo de andamento da varredura.

**Tech Stack:** Python 3.14 (pytest), GJS / GNOME Shell 50 (St, Clutter, PanelMenu), Node 22 (`node --test` só para as regras puras da extensão).

**Spec:** `docs/superpowers/specs/2026-11-07-extensao-gnome-design.md`

## Global Constraints

- GNOME Shell 50, Wayland; `metadata.json` com `"shell-version": ["50"]`.
- UUID: `guarnicao@eduardomilani8.github.io`; pasta `extensao/guarnicao@eduardomilani8.github.io/`.
- Só tema escuro. Referências visuais: `design/telas/barra-v2.html` e `design/telas/avisos-v3-muralha.html`.
- Comandos sempre como lista de argumentos (Python `subprocess` sem shell; JS `Gio.SubprocessLauncher.spawnv`). Nada de shell.
- Texto vindo de arquivo (nomes, caminhos) é sempre texto: `St.Label({text})`, nunca markup.
- Sem a extensão, os avisos continuam os comuns do GNOME, com o mesmo título e corpo.
- Plano B: se `Main.notificationDaemon._fdoNotificationDaemon.NotifyAsync` ou `Main.messageTray._showNotification` não existirem, a extensão não mexe nos avisos.
- Fontes embutidas (Fraunces, Source Sans 3, Source Code Pro), nada vindo da internet.
- Commits separados por assunto, mensagem em português, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push só com o OK do usuário.
- Testes Python: `.venv/bin/pytest -q` (a suíte inteira deve continuar passando).

## Review Focus

1. Nome de arquivo malicioso no aviso (`$(rm -rf ~).pdf`, `<b>x</b>`, quebra de linha): continua texto no `notify-send` e no cartão. Teste na Task 1 (Python) e na Task 8 (regras JS: `lerDados` não interpreta nada).
2. Varredura que morreu no meio deixa `progresso.json` para trás: o escudo não pode ficar preso em "procurando". Teste na Task 4 (`ler()` ignora pid morto).
3. Clicar em Trancar depois que o arquivo mudou ou sumiu: recusa, sem trancar outra coisa, e avisa. Teste na Task 5.
4. Clicar em "Abrir painel" com o launcher já aberto: abre o navegador no painel existente em vez de falhar com "porta ocupada". Teste na Task 7.
5. "Parar varredura" quando a varredura roda dentro do launcher: não pode matar o launcher. Teste na Task 4 (`pode_parar` falso se o processo não é `guarnicao varrer`).

---

### Task 1: Dados escondidos nos avisos

**Files:**
- Modify: `guarnicao/notificacao.py`
- Test: `tests/test_notificacao.py`

**Interfaces:**
- Produces: `comando(titulo, corpo, urgente=False, discreto=False, dados: dict[str, str] | None = None) -> list[str]`; `notificar(titulo, corpo, urgente=False, discreto=False, dados=None)`; `personagem(camada: str | None) -> str`; `dados_de(resultado, tipo: str, quarentena: str | None = None) -> dict[str, str]`; constante `CHAVES = ("tipo", "personagem", "arquivo", "caminho", "sha256", "quarentena")`. Regra do corpo: quando há `arquivo`, a primeira linha do corpo é o nome do arquivo.

- [ ] **Step 1: Write the failing tests** (acrescentar em `tests/test_notificacao.py`)

```python
def test_dados_viram_hints_de_texto():
    cmd = notificacao.comando("Ameaça encontrada", "x.exe\nEICAR", urgente=True,
                              dados={"tipo": "ameaca", "arquivo": "$(rm -rf ~).pdf", "sha256": ""})
    assert "--hint=string:x-guarnicao-tipo:ameaca" in cmd
    assert "--hint=string:x-guarnicao-arquivo:$(rm -rf ~).pdf" in cmd   # um argumento só, sem shell
    assert not any("x-guarnicao-sha256" in a for a in cmd)              # vazio não vai
    assert cmd[-2:] == ["Ameaça encontrada", "x.exe\nEICAR"]


def test_chave_desconhecida_e_recusada():
    import pytest
    with pytest.raises(ValueError):
        notificacao.comando("t", "c", dados={"comando": "rm"})


def test_personagem_pela_camada():
    assert notificacao.personagem("hash") == "cavaleiro"
    assert notificacao.personagem("clamav") == "cavaleiro"
    assert notificacao.personagem("yara") == "arqueira"
    assert notificacao.personagem("heuristica") == "vidente"
    assert notificacao.personagem(None) == "cavaleiro"


def test_dados_de_um_resultado():
    from pathlib import Path
    from guarnicao.scanner import Resultado
    r = Resultado(caminho=Path("/home/x/Downloads/fatura.pdf.exe"), sha256="ab" * 32,
                  ameaca="EICAR", camada="yara")   # infectado é propriedade: vem de `ameaca`
    d = notificacao.dados_de(r, "ameaca")
    assert d == {"tipo": "ameaca", "personagem": "arqueira", "arquivo": "fatura.pdf.exe",
                 "caminho": "/home/x/Downloads/fatura.pdf.exe", "sha256": "ab" * 32, "quarentena": ""}
    assert notificacao.dados_de(r, "trancado", "id1")["personagem"] == "carcereiro"
```

`Resultado` (em `guarnicao/scanner.py`) tem os campos `caminho`, `sha256`, `ameaca`, `pontuacao`, `motivos` e `camada`; `infectado` e `suspeito` são propriedades.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_notificacao.py`
Expected: FAIL (`unexpected keyword argument 'dados'`, `no attribute 'personagem'`).

- [ ] **Step 3: Implement** em `guarnicao/notificacao.py`

```python
CHAVES = ("tipo", "personagem", "arquivo", "caminho", "sha256", "quarentena")
PERSONAGEM_DA_CAMADA = {"hash": "cavaleiro", "clamav": "cavaleiro", "virustotal": "cavaleiro",
                        "yara": "arqueira", "heuristica": "vidente"}


def personagem(camada: str | None) -> str:
    """Quem aparece no aviso: quem reconheceu a ameaça (assinaturas = Cavaleiro)."""
    return PERSONAGEM_DA_CAMADA.get(camada or "", "cavaleiro")


def dados_de(resultado, tipo: str, quarentena: str | None = None) -> dict[str, str]:
    """Os dados escondidos de um aviso sobre um arquivo (scanner.Resultado)."""
    return {
        "tipo": tipo,
        "personagem": "carcereiro" if tipo == "trancado" else personagem(resultado.camada),
        "arquivo": resultado.caminho.name,
        "caminho": str(resultado.caminho),
        "sha256": resultado.sha256 or "",
        "quarentena": quarentena or "",
    }


def _hints(dados: dict[str, str] | None) -> list[str]:
    # A extensão do GNOME lê estes hints para desenhar o cartão da muralha. Cada um
    # é um argumento só (sem shell); o notify-send separa TIPO:NOME:VALOR nos dois
    # primeiros ":" e o resto do valor fica intacto.
    saida = []
    for chave, valor in (dados or {}).items():
        if chave not in CHAVES:
            raise ValueError(f"dado de aviso desconhecido: {chave}")
        if valor:
            saida.append(f"--hint=string:x-guarnicao-{chave}:{valor}")
    return saida
```

Em `comando`, acrescente o parâmetro `dados: dict[str, str] | None = None` e troque o `return` por:

```python
    return ["notify-send", "--app-name=Guarnição", *opcoes, *_hints(dados), titulo, corpo]
```

Em `notificar`, acrescente `dados: dict[str, str] | None = None` e passe adiante nas duas chamadas a `comando(...)`: `comando(titulo, corpo, urgente, discreto, dados)`. Em `resumo_limpo`, troque a chamada por `notificar(*texto_resumo_limpo(nome, total, quando), discreto=True, dados={"tipo": "limpa"})`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/test_notificacao.py`
Expected: PASS. Depois `.venv/bin/pytest -q`: tudo passa.

- [ ] **Step 5: Commit**

```bash
git add guarnicao/notificacao.py tests/test_notificacao.py
git commit -m "Avisos: dados escondidos (hints) para a extensão do GNOME desenhar o cartão"
```

---

### Task 2: Quem avisa passa os dados

**Files:**
- Modify: `guarnicao/__main__.py` (`cmd_varrer` ~linha 178, `cmd_monitorar` ~linhas 293-317, `cmd_proteger` ~linhas 350-366)
- Test: `tests/test_historico.py`, `tests/test_notificacao.py`

**Interfaces:**
- Consumes: `notificacao.dados_de`, `notificacao.notificar(..., dados=...)` (Task 1).
- Produces: avisos com `tipo` em {`ameaca`, `varias`, `suspeito`, `trancado`, `bloqueado`, `limpa`}; corpo começando pelo nome do arquivo quando há `arquivo`.

- [ ] **Step 1: Write the failing tests**

Em `tests/test_historico.py`, troque o fim de `test_agendada_avisa_e_nao_falha` para conferir os dados:

```python
    [((titulo, corpo), opcoes)] = avisos
    assert "1 ameaça(s)" in titulo and opcoes["urgente"]
    assert opcoes["dados"]["tipo"] == "ameaca" and opcoes["dados"]["arquivo"] == "teste.com"
    assert corpo.splitlines()[0] == "teste.com"
    assert historico.listar()[0].origem == "agendada"
    assert (pasta / "teste.com").exists()        # agendada não isola sozinha
```

E acrescente:

```python
def test_agendada_com_varios_achados_e_um_aviso_so(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "a.com").write_bytes(EICAR)
    (pasta / "b.com").write_bytes(EICAR + b" ")
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    rodar(monkeypatch, "varrer", str(pasta), "--agendada", "--processos", "1")
    [((titulo, corpo), opcoes)] = avisos
    assert opcoes["dados"] == {"tipo": "varias"} and "launcher" in corpo
```

Se o segundo EICAR com espaço não for detectado, use dois arquivos com o mesmo conteúdo e nomes diferentes.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_historico.py`
Expected: FAIL (`KeyError: 'dados'`).

- [ ] **Step 3: Implement**

Em `cmd_varrer`, no bloco `if args.agendada:`, troque o aviso de achados por:

```python
        if resumo.ameacas or resumo.suspeitos:
            titulo = f"Varredura {nome}: {resumo.ameacas} ameaça(s), {resumo.suspeitos} suspeito(s)"
            if len(achados) == 1:
                a = achados[0]
                tipo = "ameaca" if a["veredito"] == "ameaca" else "suspeito"
                nome_arquivo = Path(a["caminho"]).name
                corpo = f"{nome_arquivo}\n{a['ameaca'] or 'suspeito'} · abra o painel para trancar"
                dados = {"tipo": tipo, "personagem": notificacao.personagem(a.get("camada")),
                         "arquivo": nome_arquivo, "caminho": a["caminho"], "sha256": a.get("sha256") or ""}
            else:
                corpo = "Abra o launcher para ver e trancar: python -m guarnicao launcher"
                dados = {"tipo": "varias"}
            notificacao.notificar(titulo, corpo, urgente=bool(resumo.ameacas), dados=dados)
```

Em `cmd_monitorar`, `ao_analisar`:

```python
        if item.infectado:
            if id_:
                notificacao.notificar("Trancado na quarentena", f"{item.caminho.name}\n{item.ameaca}",
                                      urgente=True, dados=notificacao.dados_de(item, "trancado", id_))
            else:
                notificacao.notificar("Ameaça encontrada", f"{item.caminho.name}\n{item.ameaca}",
                                      urgente=True, dados=notificacao.dados_de(item, "ameaca"))
        elif item.suspeito:
            notificacao.notificar(
                f"Arquivo suspeito ({item.pontuacao}/100)",
                f"{item.caminho.name}\n{item.motivos[0] if item.motivos else ''}",
                dados=notificacao.dados_de(item, "suspeito"),
            )
```

Em `ao_alertar`:

```python
        exe = Path(alerta.processo.exe)
        notificacao.notificar(f"Comportamento perigoso: {alerta.tipo}", f"{exe.name}\n{alerta.mensagem}",
                              urgente=alerta.gravidade == "alta",
                              dados={"tipo": "suspeito", "personagem": "vidente",
                                     "arquivo": exe.name, "caminho": str(exe)})
```

Em `cmd_proteger`, `ao_decidir`: nos quatro `notificar`, passe `dados` e deixe a primeira linha do corpo como o nome do arquivo:

```python
        caminho = Path(d.caminho)
        base = {"personagem": notificacao.personagem(d.resultado.camada if d.resultado else None),
                "arquivo": caminho.name, "caminho": str(caminho),
                "sha256": (d.resultado.sha256 if d.resultado else None) or ""}
```

e então, em cada ramo, `dados=base | {"tipo": "bloqueado"}` (bloqueado), `base | {"tipo": "ameaca"}` (só avisar e prazo) e `base | {"tipo": "suspeito"}` (suspeito), com o corpo `f"{caminho.name}\n{nome}"` (mais a linha do `sudo kill` no prazo, e o motivo no suspeito).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add guarnicao/__main__.py tests/test_historico.py
git commit -m "Avisos: varredura, monitor, comportamento e protetor mandam os dados do cartão"
```

---

### Task 3: Aviso de bases desatualizadas (uma vez por dia)

**Files:**
- Modify: `guarnicao/notificacao.py`, `guarnicao/__main__.py` (`cmd_monitorar`, laço `while True`)
- Test: `tests/test_notificacao.py`

**Interfaces:**
- Produces: `uma_vez_por_dia(marca: Path, quando: datetime) -> bool`; `aviso_bases(avisos: list[str], freshclam_parado: bool, quando: datetime, marca: Path | None = None) -> bool`; constante `MARCA_BASES`.

- [ ] **Step 1: Write the failing tests**

```python
def test_aviso_de_bases_uma_vez_por_dia(tmp_path, monkeypatch):
    from datetime import datetime
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    marca = tmp_path / "ultimo-aviso-bases"
    dia = datetime(2026, 11, 8, 9, 0)
    assert not notificacao.aviso_bases([], False, dia, marca)              # tudo em dia: silêncio
    assert notificacao.aviso_bases(["yara-forge: sem atualizar há 9 dia(s)"], False, dia, marca)
    assert not notificacao.aviso_bases(["yara-forge: sem atualizar há 9 dia(s)"], False, dia, marca)
    assert notificacao.aviso_bases([], True, datetime(2026, 11, 9, 9, 0), marca)
    (titulo, corpo), opcoes = avisos[0]
    assert titulo == "Suas bases estão desatualizadas" and "yara-forge" in corpo
    assert opcoes["dados"] == {"tipo": "bases", "personagem": "cavaleiro"}
    assert "freshclam" in avisos[1][0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_notificacao.py`
Expected: FAIL (`no attribute 'aviso_bases'`).

- [ ] **Step 3: Implement** em `guarnicao/notificacao.py`

Troque o corpo de `resumo_limpo` para usar o auxiliar e acrescente o aviso de bases:

```python
MARCA_BASES = MARCA_RESUMO.with_name("ultimo-aviso-bases")


def uma_vez_por_dia(marca: Path, quando: datetime) -> bool:
    """True se ainda não marcou hoje (e marca). Sem onde gravar, deixa avisar."""
    hoje = quando.date().isoformat()
    try:
        if marca.read_text().strip() == hoje:
            return False
    except OSError:
        pass
    try:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(hoje)
    except OSError:
        pass
    return True


def resumo_limpo(nome: str, total: int, quando: datetime, marca: Path | None = None) -> bool:
    """(docstring atual)"""
    if not uma_vez_por_dia(marca or MARCA_RESUMO, quando):
        return False
    notificar(*texto_resumo_limpo(nome, total, quando), discreto=True, dados={"tipo": "limpa"})
    return True


def aviso_bases(avisos: list[str], freshclam_parado: bool, quando: datetime,
                marca: Path | None = None) -> bool:
    """Bases velhas ou freshclam parado: avisa no máximo uma vez por dia (avisos-v3)."""
    if not avisos and not freshclam_parado:
        return False
    if not uma_vez_por_dia(marca or MARCA_BASES, quando):
        return False
    corpo = avisos[0] if avisos else "O serviço do ClamAV que baixa assinaturas (freshclam) está parado."
    notificar("Suas bases estão desatualizadas", corpo, dados={"tipo": "bases", "personagem": "cavaleiro"})
    return True
```

Em `cmd_monitorar`, troque o laço por uma conferência de hora em hora (o monitor está sempre ligado; o timer das bases pode ter parado):

```python
        try:
            conferido = 0.0
            while True:
                time.sleep(1)
                if time.monotonic() - conferido > 3600:
                    conferido = time.monotonic()
                    from datetime import datetime
                    notificacao.aviso_bases(bases.avisos(), bases.freshclam_parado(), datetime.now())
        except KeyboardInterrupt:
```

Confira se `bases` já está importado no topo de `__main__.py`; se não, use `from . import bases` dentro da função.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add guarnicao/notificacao.py guarnicao/__main__.py tests/test_notificacao.py
git commit -m "Avisos: bases desatualizadas avisam no máximo uma vez por dia, pelo monitor"
```

---

### Task 4: Arquivo de andamento da varredura

**Files:**
- Create: `guarnicao/andamento.py`
- Modify: `guarnicao/varredura.py` (`executar`), `guarnicao/__main__.py` (`cmd_varrer` e parser de `varrer`), `guarnicao/launcher/servidor.py` (`_transmitir`)
- Test: `tests/test_andamento.py`

**Interfaces:**
- Produces: `andamento.ARQUIVO: Path`; `gravar(tipo: str, feitos: int, total: int, arquivo: Path | None = None) -> None`; `apagar(arquivo: Path | None = None) -> None`; `ler(arquivo: Path | None = None) -> dict | None` (chaves `pid`, `tipo`, `feitos`, `total`, `pode_parar`); `parar(arquivo: Path | None = None) -> bool`; `varredura.executar(..., rotulo: str | None = None)`; CLI `guarnicao varrer --parar`.

- [ ] **Step 1: Write the failing tests** (`tests/test_andamento.py`)

```python
import json
import os
import subprocess
import sys

from guarnicao import andamento, varredura


def test_grava_le_e_apaga(tmp_path):
    arq = tmp_path / "progresso.json"
    andamento.gravar("rápida", 183, 305, arq)
    d = andamento.ler(arq)
    assert (d["tipo"], d["feitos"], d["total"], d["pid"]) == ("rápida", 183, 305, os.getpid())
    andamento.apagar(arq)
    assert andamento.ler(arq) is None


def test_pid_morto_e_ignorado(tmp_path):
    arq = tmp_path / "progresso.json"
    morto = subprocess.Popen([sys.executable, "-c", "pass"])
    morto.wait()
    arq.write_text(json.dumps({"pid": morto.pid, "tipo": "rápida", "feitos": 1, "total": 9}))
    assert andamento.ler(arq) is None          # varredura que morreu não prende o escudo


def test_so_para_processo_de_varredura(tmp_path):
    arq = tmp_path / "progresso.json"
    andamento.gravar("rápida", 1, 9, arq)      # este processo é o pytest, não "guarnicao varrer"
    assert andamento.ler(arq)["pode_parar"] is False
    assert andamento.parar(arq) is False       # nunca mata o launcher nem outro programa


def test_executar_com_rotulo_grava_e_apaga(tmp_path, monkeypatch):
    arq = tmp_path / "progresso.json"
    monkeypatch.setattr(andamento, "ARQUIVO", arq)
    (tmp_path / "pasta").mkdir()
    (tmp_path / "pasta" / "a.txt").write_text("oi")
    vistos = []
    for item in varredura.executar([tmp_path / "pasta"], varredura.Exclusoes(), usar_cache=False,
                                   processos=1, rotulo="rápida"):
        if isinstance(item, varredura.Progresso):
            vistos.append(andamento.ler(arq) is not None)
    assert any(vistos) and not arq.exists()


def test_executar_sem_rotulo_nao_grava(tmp_path, monkeypatch):
    arq = tmp_path / "progresso.json"
    monkeypatch.setattr(andamento, "ARQUIVO", arq)
    (tmp_path / "pasta").mkdir()
    list(varredura.executar([tmp_path / "pasta"], varredura.Exclusoes(), usar_cache=False, processos=1))
    assert not arq.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_andamento.py`
Expected: FAIL (`No module named 'guarnicao.andamento'`).

- [ ] **Step 3: Implement** `guarnicao/andamento.py`

```python
"""O andamento da varredura que está rodando, para o escudo da barra ir enchendo.

Um arquivo pequeno em ~/.cache/guarnicao/progresso.json, gravado durante a
varredura e apagado no fim. Se a varredura morrer no meio, o pid dele não
existe mais e ler() devolve None: o escudo nunca fica preso em "procurando".
"""

import json
import os
import signal
from pathlib import Path

from .caminhos import casa_real

ARQUIVO = Path(os.environ.get("XDG_CACHE_HOME", casa_real() / ".cache")) / "guarnicao" / "progresso.json"


def gravar(tipo: str, feitos: int, total: int, arquivo: Path | None = None) -> None:
    arquivo = arquivo or ARQUIVO
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps({"pid": os.getpid(), "tipo": tipo, "feitos": feitos, "total": total}))
        temporario.replace(arquivo)
    except OSError:
        pass   # sem andamento o escudo só não enche; a varredura segue


def apagar(arquivo: Path | None = None) -> None:
    try:
        (arquivo or ARQUIVO).unlink()
    except OSError:
        pass


def _linha_de_comando(pid: int) -> list[str]:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


def ler(arquivo: Path | None = None) -> dict | None:
    try:
        dados = json.loads((arquivo or ARQUIVO).read_text())
        pid = int(dados["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    comando = _linha_de_comando(pid)
    if not comando or not Path(f"/proc/{pid}").exists():
        return None
    # Só a varredura do terminal ou do timer pode ser parada: a do launcher roda
    # dentro dele, e parar o pid seria fechar o painel.
    dados["pode_parar"] = "guarnicao" in comando and "varrer" in comando
    return dados


def parar(arquivo: Path | None = None) -> bool:
    dados = ler(arquivo)
    if not dados or not dados["pode_parar"]:
        return False
    try:
        os.kill(int(dados["pid"]), signal.SIGTERM)
    except OSError:
        return False
    return True
```

Em `guarnicao/varredura.py`: renomeie a função atual `executar` para `_executar` (mesmos parâmetros, mesmo corpo) e acrescente acima dela:

```python
def executar(
    raizes: list[Path],
    exclusoes: Exclusoes | None = None,
    usar_cache: bool = True,
    processos: int | None = None,
    cache: Cache | None = None,
    rotulo: str | None = None,
) -> Iterator[Progresso | scanner.Resultado | tuple[Path, OSError] | Resumo]:
    """Varre as raízes. Com `rotulo` (ex.: "rápida"), grava o andamento para o
    escudo da barra e apaga no fim, inclusive se a varredura for interrompida."""
    try:
        for item in _executar(raizes, exclusoes, usar_cache, processos, cache):
            if rotulo and isinstance(item, Progresso):
                andamento.gravar(rotulo, item.vistos, item.total)
            yield item
    finally:
        if rotulo:
            andamento.apagar()
```

e inclua `andamento` no `from . import ...` do topo.

Em `cmd_varrer`, passe `rotulo=nome` na chamada a `varredura.executar(...)`, e no começo da função:

```python
    if args.parar:
        from . import andamento
        if andamento.parar():
            print("Pedi para a varredura parar.")
            return 0
        print("Nenhuma varredura do terminal ou do timer está rodando.")
        return 1
```

Para a varredura parar limpa (apagando o andamento), registre antes de varrer: `signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))` e confira que `cmd_varrer` trata `KeyboardInterrupt` saindo com código 130; se não tratar, envolva o laço da varredura em `try/except KeyboardInterrupt: print("\nVarredura interrompida."); return 130`.

No parser de `varrer`: `p_varrer.add_argument("--parar", action="store_true", help="para a varredura do terminal ou do timer que está rodando")`, e faça o `alvo` ser opcional quando `--parar` é usado (a validação "Diga o que varrer" já existe e vem depois do `if args.parar`).

Em `guarnicao/launcher/servidor.py`, `_transmitir`: passe `rotulo=rotulo` (o parâmetro que já existe) na chamada a `varredura.executar(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add guarnicao/andamento.py guarnicao/varredura.py guarnicao/__main__.py guarnicao/launcher/servidor.py tests/test_andamento.py
git commit -m "Varredura: grava o andamento para o escudo e aceita --parar"
```

---

### Task 5: Trancar pelo aviso

**Files:**
- Create: `guarnicao/trancar.py`
- Modify: `guarnicao/launcher/servidor.py` (`isolar`), `guarnicao/__main__.py` (`cmd_quarentena` e parser)
- Test: `tests/test_trancar.py`

**Interfaces:**
- Produces: `trancar.Recusa(Exception)` com `.status: int`, `.motivo: str`; `trancar.trancar(caminho: str, sha256: str, ameaca: str | None = None, camada: str | None = None, veredito: str = "ameaca") -> str` (id da quarentena); `trancar.do_historico(caminho: str, sha256: str) -> dict` (`ameaca`, `camada`, `veredito`, ou `{}`); CLI `guarnicao quarentena trancar CAMINHO --sha256 HASH`.

- [ ] **Step 1: Write the failing tests** (`tests/test_trancar.py`)

```python
import pytest

from guarnicao import __main__ as cli
from guarnicao import notificacao, quarentena, scanner, trancar

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@pytest.fixture(autouse=True)
def quarentena_isolada(tmp_path, monkeypatch):
    monkeypatch.setattr(quarentena, "PASTA_PADRAO", tmp_path / "quarentena")


def test_tranca_o_mesmo_arquivo(tmp_path):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    id_ = trancar.trancar(str(arq), scanner.calcular_sha256(arq), "EICAR", "hash")
    assert not arq.exists() and id_ in {e["id"] for e in quarentena.listar()}


def test_recusa_arquivo_que_mudou(tmp_path):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    sha = scanner.calcular_sha256(arq)
    arq.write_bytes(b"outra coisa")
    with pytest.raises(trancar.Recusa) as e:
        trancar.trancar(str(arq), sha)
    assert e.value.status == 409 and arq.exists()


def test_recusa_link_e_arquivo_sumido(tmp_path):
    alvo = tmp_path / "alvo"
    alvo.write_bytes(EICAR)
    link = tmp_path / "link"
    link.symlink_to(alvo)
    for caminho in (link, tmp_path / "nao-existe"):
        with pytest.raises(trancar.Recusa) as e:
            trancar.trancar(str(caminho), "0" * 64)
        assert e.value.status == 410
    assert alvo.exists()


def test_cli_tranca_e_confirma_com_desfazer(tmp_path, monkeypatch):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr("sys.argv", ["guarnicao", "quarentena", "trancar", str(arq),
                                     "--sha256", scanner.calcular_sha256(arq)])
    assert cli.main() == 0
    [((titulo, corpo), opcoes)] = avisos
    assert titulo == "Trancado na quarentena" and corpo.splitlines()[0] == "ruim.com"
    assert opcoes["dados"]["tipo"] == "trancado" and opcoes["dados"]["quarentena"]


def test_cli_recusa_avisa(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr("sys.argv", ["guarnicao", "quarentena", "trancar", str(tmp_path / "x"),
                                     "--sha256", "0" * 64])
    assert cli.main() == 2
    assert avisos[0][0][0] == "Não deu para trancar"
```

Confira em `tests/test_quarentena.py` como a quarentena é isolada nos testes existentes; se for por outra fixture ou variável, use a mesma em vez de `quarentena_isolada`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_trancar.py`
Expected: FAIL (`No module named 'guarnicao.trancar'`).

- [ ] **Step 3: Implement** `guarnicao/trancar.py`

```python
"""Trancar um achado: o mesmo para o botão do painel e o do aviso no canto.

Só tranca se o arquivo ainda é exatamente o que foi analisado (mesmo hash, não
é link): se ele mudou, a decisão precisa ser tomada de novo.
"""

from pathlib import Path

from . import historico, quarentena, scanner


class Recusa(Exception):
    def __init__(self, status: int, motivo: str):
        super().__init__(motivo)
        self.status, self.motivo = status, motivo


def trancar(caminho: str, sha256: str, ameaca: str | None = None, camada: str | None = None,
            veredito: str = "ameaca") -> str:
    arquivo = Path(caminho)
    if not arquivo.is_file() or arquivo.is_symlink():
        raise Recusa(410, "o arquivo não está mais lá")
    try:
        if scanner.calcular_sha256(arquivo) != sha256:
            raise Recusa(409, "o arquivo mudou desde a varredura: varra de novo")
        motivo = ameaca or ("suspeito" if veredito == "suspeito" else "ameaça")
        id_cela = quarentena.isolar(arquivo, sha256, motivo, camada=camada, veredito=veredito)
    except PermissionError:
        raise Recusa(403, "sem permissão: é um arquivo do sistema, use "
                          "sudo .venv/bin/python -m guarnicao varrer --isolar")
    except OSError as erro:
        raise Recusa(500, erro.strerror or str(erro))
    historico.marcar_isolado(caminho, sha256, id_cela)
    return id_cela


def do_historico(caminho: str, sha256: str) -> dict:
    """O nome da ameaça e a camada, se o achado está no histórico."""
    for registro in historico.listar(None):
        for a in registro.achados:
            if a.get("caminho") == caminho and a.get("sha256") == sha256:
                return {"ameaca": a.get("ameaca"), "camada": a.get("camada"),
                        "veredito": a.get("veredito") or "ameaca"}
    return {}
```

Em `guarnicao/launcher/servidor.py`, `isolar`, troque o bloco desde `caminho = Path(dados["caminho"])` até `historico.marcar_isolado(...)` por:

```python
    try:
        id_cela = trancar.trancar(dados["caminho"], dados["sha256"], dados["ameaca"],
                                  dados["camada"], dados["veredito"])
    except trancar.Recusa as recusa:
        raise Recusado(recusa.status, recusa.motivo)
```

e importe `trancar` no topo (`from .. import trancar`). Remova imports que ficarem sem uso.

Em `cmd_quarentena`, acrescente o ramo antes do `else`:

```python
    elif args.acao == "trancar":
        from . import trancar
        try:
            id_ = trancar.trancar(args.caminho, args.sha256, **trancar.do_historico(args.caminho, args.sha256))
        except trancar.Recusa as recusa:
            print(f"{VERMELHO}Não deu para trancar: {recusa.motivo}{FIM}")
            notificacao.notificar("Não deu para trancar", f"{Path(args.caminho).name}\n{recusa.motivo}",
                                  dados={"tipo": "suspeito", "personagem": "carcereiro",
                                         "arquivo": Path(args.caminho).name})
            return 2
        print(f"Trancado na quarentena (id {id_}): {args.caminho}")
        notificacao.notificar("Trancado na quarentena", f"{Path(args.caminho).name}\nPara devolver: Desfazer",
                              dados={"tipo": "trancado", "personagem": "carcereiro",
                                     "arquivo": Path(args.caminho).name, "quarentena": id_})
```

No parser:

```python
    q_trancar = q_sub.add_parser("trancar", help="tranca um arquivo achado (usado pelo aviso no canto)")
    q_trancar.add_argument("caminho")
    q_trancar.add_argument("--sha256", required=True, help="só tranca se o arquivo ainda tem este hash")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: PASS (inclusive os testes do launcher que já cobrem `/api/isolar`).

- [ ] **Step 5: Commit**

```bash
git add guarnicao/trancar.py guarnicao/launcher/servidor.py guarnicao/__main__.py tests/test_trancar.py
git commit -m "Quarentena: trancar pelo aviso, com a mesma regra do painel"
```

---

### Task 6: `guarnicao estado --json`

**Files:**
- Create: `guarnicao/escudo.py`
- Modify: `guarnicao/__main__.py` (comando `estado`)
- Test: `tests/test_escudo.py`

**Interfaces:**
- Consumes: `launcher.estado.montar()` (dict com `protetor`, `monitor`, `bases`), `historico.listar`, `historico.pendentes`, `andamento.ler()` (Task 4).
- Produces: `escudo.montar(servicos: dict, registros: list[historico.Registro], progresso: dict | None, agora: datetime) -> dict` com chaves `estado` (`certo|procurando|atencao|ameaca`), `titulo`, `linhas: list[str]`, `acoes: list[str]` (de `varrer|abrir|trancar|atualizar|parar`) e `nivel: int` (1-4, só em `procurando`); CLI `guarnicao estado --json`.

- [ ] **Step 1: Write the failing tests** (`tests/test_escudo.py`)

```python
from datetime import datetime

from guarnicao import escudo, historico, varredura

AGORA = datetime(2026, 11, 8, 12, 40)


def servicos(protetor=True, monitor=True, avisos=(), freshclam=False):
    return {"protetor": {"instalado": True, "ativo": protetor, "ligar": "sudo systemctl enable --now guarnicao-protetor"},
            "monitor": {"instalado": True, "ativo": monitor, "ligar": "systemctl --user enable --now guarnicao-monitor"},
            "bases": {"conferidas": AGORA.timestamp() - 180, "avisos": list(avisos), "freshclam_parado": freshclam}}


def registro(achados=(), total=305, quando="2026-11-08T12:30:00"):
    resumo = varredura.Resumo(analisados=total, ameacas=sum(a["veredito"] == "ameaca" for a in achados))
    return historico.novo("rápida", "agendada", datetime.fromisoformat(quando), resumo, list(achados))


def test_tudo_certo():
    e = escudo.montar(servicos(), [registro()], None, AGORA)
    assert e["estado"] == "certo" and e["titulo"] == "Você está protegido"
    assert e["linhas"][:2] == ["Última: rápida · hoje, 12:30", "✓ 305 arquivos, tudo limpo"]
    assert e["acoes"] == ["varrer", "abrir"]


def test_procurando_enche_em_passos():
    e = escudo.montar(servicos(), [registro()], {"feitos": 183, "total": 305, "pode_parar": True}, AGORA)
    assert e["estado"] == "procurando" and e["nivel"] == 3
    assert e["linhas"][0] == "183 de 305 arquivos · 60%"
    assert e["acoes"] == ["abrir", "parar"]


def test_atencao_bases_velhas():
    e = escudo.montar(servicos(avisos=["yara-forge: sem atualizar há 9 dia(s)"]), [registro()], None, AGORA)
    assert e["estado"] == "atencao" and e["titulo"] == "Suas bases estão desatualizadas"
    assert e["acoes"] == ["atualizar", "abrir"]


def test_atencao_protetor_parado():
    e = escudo.montar(servicos(protetor=False), [registro()], None, AGORA)
    assert e["estado"] == "atencao" and "protetor" in e["titulo"].lower()


def test_ameaca_vence_tudo(tmp_path):
    arq = tmp_path / "ruim.exe"
    arq.write_text("x")
    achado = {"caminho": str(arq), "veredito": "ameaca", "ameaca": "EICAR", "camada": "hash",
              "sha256": "a" * 64, "quarentena": None}
    e = escudo.montar(servicos(protetor=False, avisos=["x"]), [registro([achado])],
                      {"feitos": 1, "total": 9, "pode_parar": True}, AGORA)
    assert e["estado"] == "ameaca" and e["titulo"] == "1 arquivo perigoso"
    assert e["acoes"][0] == "trancar"


def test_sem_varredura_ainda():
    e = escudo.montar(servicos(), [], None, AGORA)
    assert e["estado"] == "certo" and "Nenhuma varredura ainda" in e["linhas"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_escudo.py`
Expected: FAIL (`No module named 'guarnicao.escudo'`).

- [ ] **Step 3: Implement** `guarnicao/escudo.py`

```python
"""O que o escudo da barra do GNOME mostra (design/telas/barra-v2.html).

Um estado só, na ordem de prioridade: ameaça não tratada > procurando >
precisa de atenção > tudo certo. Só lê; quem age são os botões do menu.
"""

import math
from datetime import datetime


def quando(instante: datetime, agora: datetime) -> str:
    dias = (agora.date() - instante.date()).days
    dia = "hoje" if dias == 0 else "ontem" if dias == 1 else instante.strftime("%d/%m")
    return f"{dia}, {instante:%H:%M}"


def ha_quanto(segundos: float) -> str:
    if segundos < 3600:
        return f"há {max(1, int(segundos // 60))} min"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    return f"há {int(segundos // 86400)} dia(s)"


def _ultima(registros, agora: datetime) -> list[str]:
    if not registros:
        return ["Nenhuma varredura ainda"]
    r = registros[0]
    resultado = (f"✓ {r.total} arquivos, tudo limpo" if not (r.ameacas or r.suspeitos)
                 else f"{r.ameacas} ameaça(s) · {r.suspeitos} suspeito(s)")
    return [f"Última: {r.tipo} · {quando(r.quando, agora)}", resultado]


def montar(servicos: dict, registros: list, progresso: dict | None, agora: datetime) -> dict:
    from . import historico
    perigosos = historico.pendentes(registros)
    if perigosos:
        n = len(perigosos)
        titulo = "1 arquivo perigoso" if n == 1 else f"{n} arquivos perigosos"
        r, _ = perigosos[0]
        return {"estado": "ameaca", "titulo": titulo,
                "linhas": [f"{n} ameaça(s) no lugar", f"Varredura {r.tipo} · {quando(r.quando, agora)}"],
                "acoes": ["trancar", "varrer"]}

    if progresso and progresso.get("total"):
        feitos, total = progresso["feitos"], progresso["total"]
        pct = min(100, round(100 * feitos / total))
        return {"estado": "procurando", "titulo": "Procurando ameaças…", "nivel": max(1, math.ceil(pct / 25)),
                "linhas": [f"{feitos} de {total} arquivos · {pct}%", "Nada encontrado até agora"],
                "acoes": ["abrir", "parar"] if progresso.get("pode_parar") else ["abrir"]}

    bases = servicos.get("bases", {})
    if bases.get("avisos") or bases.get("freshclam_parado"):
        linhas = list(bases.get("avisos") or [])[:2] or ["O serviço do ClamAV (freshclam) está parado"]
        return {"estado": "atencao", "titulo": "Suas bases estão desatualizadas", "linhas": linhas,
                "acoes": ["atualizar", "abrir"]}
    for nome, rotulo in (("protetor", "O protetor está desligado"), ("monitor", "O monitor está desligado")):
        s = servicos.get(nome, {})
        if s.get("instalado") and not s.get("ativo"):
            return {"estado": "atencao", "titulo": rotulo, "linhas": [f"Para ligar: {s.get('ligar', '')}"],
                    "acoes": ["abrir"]}

    linhas = _ultima(registros, agora)
    if bases.get("conferidas"):
        linhas.append(f"Bases atualizadas {ha_quanto(agora.timestamp() - bases['conferidas'])}")
    return {"estado": "certo", "titulo": "Você está protegido", "linhas": linhas, "acoes": ["varrer", "abrir"]}
```

Em `guarnicao/__main__.py`:

```python
def cmd_estado(args) -> int:
    from datetime import datetime

    from . import andamento, escudo, historico
    from .launcher import estado
    dados = escudo.montar(estado.montar(), historico.listar(50), andamento.ler(), datetime.now())
    if args.json:
        print(json.dumps(dados, ensure_ascii=False))
    else:
        print(dados["titulo"])
        for linha in dados["linhas"]:
            print(f"  {linha}")
    return 0
```

e no parser: `p_e = sub.add_parser("estado", help="o estado em uma linha (o escudo da barra usa --json)")`, `p_e.add_argument("--json", action="store_true")`, `p_e.set_defaults(func=cmd_estado)`. Importe `json` no topo se ainda não estiver.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q` e, ao vivo, `.venv/bin/python -m guarnicao estado --json`.
Expected: PASS; o comando imprime um JSON com `"estado": "certo"` (ou o estado real desta máquina).

- [ ] **Step 5: Commit**

```bash
git add guarnicao/escudo.py guarnicao/__main__.py tests/test_escudo.py
git commit -m "Escudo: guarnicao estado --json, com a prioridade da barra-v2"
```

---

### Task 7: "Abrir painel" com o launcher já aberto

**Files:**
- Modify: `guarnicao/__main__.py` (`cmd_launcher`)
- Test: `tests/test_launcher.py`

**Interfaces:**
- Produces: `guarnicao launcher` devolve 0 e abre o navegador no painel existente quando a porta já está com um launcher da Guarnição.

- [ ] **Step 1: Write the failing test** (acrescentar em `tests/test_launcher.py`)

```python
def test_launcher_ja_aberto_so_abre_o_navegador(monkeypatch):
    import threading

    from guarnicao import __main__ as cli
    from guarnicao.launcher import servidor
    srv = servidor.criar_servidor(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    abertos = []
    monkeypatch.setattr("webbrowser.open", abertos.append)
    try:
        monkeypatch.setattr("sys.argv", ["guarnicao", "launcher", "--porta", str(srv.server_address[1])])
        assert cli.main() == 0
    finally:
        srv.shutdown()
        srv.server_close()
    assert abertos == [f"http://127.0.0.1:{srv.server_address[1]}/"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/test_launcher.py -k ja_aberto`
Expected: FAIL (devolve 2, "Não consegui abrir a porta").

- [ ] **Step 3: Implement** em `cmd_launcher`, troque o `except OSError` por:

```python
    except OSError as erro:
        url = f"http://127.0.0.1:{args.porta}/"
        if erro.errno == errno.EADDRINUSE and _launcher_responde(url):
            # O botão do aviso ou do escudo chama "launcher" de novo: reaproveita o painel aberto.
            print(f"{VERDE}O painel já está aberto em {url}{FIM}")
            if not args.sem_navegador:
                webbrowser.open(url)
            return 0
        print(f"{VERMELHO}Não consegui abrir a porta {args.porta}: {erro.strerror}{FIM}")
        return 2
```

e acima de `cmd_launcher`:

```python
def _launcher_responde(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url + "api/estado", timeout=2) as resposta:
            return resposta.status == 200
    except OSError:
        return False
```

Importe `errno` no topo se ainda não estiver.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add guarnicao/__main__.py tests/test_launcher.py
git commit -m "Launcher: se já está aberto, só abre o navegador nele"
```

---

### Task 8: Esqueleto da extensão, arte e regras puras

**Files:**
- Create: `extensao/construir_arte.py`
- Create: `extensao/guarnicao@eduardomilani8.github.io/metadata.json`
- Create: `extensao/guarnicao@eduardomilani8.github.io/regras.js`
- Create: `extensao/guarnicao@eduardomilani8.github.io/arte/*` (gerados pelo script e commitados)
- Test: `tests/test_arte_extensao.py`, `extensao/testes/regras.test.mjs`

**Interfaces:**
- Produces: arte `cavaleiro.svg`, `arqueira.svg`, `vidente.svg`, `carcereiro.svg` (240×300), `escudo-certo.svg`, `escudo-atencao.svg`, `escudo-ameaca.svg`, `escudo-procurando-1..4.svg` (16×16, traço branco), `ameia.svg` (426×16). `regras.js` exporta `lerDados(hints) -> object|null`, `detalhe(dados, corpo) -> string`, `botoes(dados) -> [{rotulo, args, principal?}]`, `TOM`, `FRASE`, `NOMES`, `ROTULOS_MENU`, `COMANDOS_MENU`.

- [ ] **Step 1: Write the failing tests**

`tests/test_arte_extensao.py`:

```python
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "extensao"))
import construir_arte  # noqa: E402


def referencias_resolvidas(svg: str) -> bool:
    ET.fromstring(svg)   # XML válido
    ids = set(re.findall(r'\sid="([^"]+)"', svg))
    usados = set(re.findall(r'href="#([^"]+)"', svg)) | set(re.findall(r'url\(#([^)]+)\)', svg))
    return usados <= ids


def test_retratos_sozinhos():
    for nome in ("cavaleiro", "arqueira", "vidente", "carcereiro"):
        svg = construir_arte.retrato(nome)
        assert 'width="240"' in svg and referencias_resolvidas(svg), nome


def test_escudos_da_barra():
    escudos = construir_arte.escudos()
    assert set(escudos) == {"escudo-certo", "escudo-atencao", "escudo-ameaca",
                            *(f"escudo-procurando-{n}" for n in range(1, 5))}
    for svg in escudos.values():
        assert "currentColor" not in svg and referencias_resolvidas(svg)
```

`extensao/testes/regras.test.mjs`:

```js
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {lerDados, detalhe, botoes, ROTULOS_MENU, COMANDOS_MENU} from '../guarnicao@eduardomilani8.github.io/regras.js';

test('só os hints da Guarnição, sempre como texto', () => {
    const d = lerDados({'x-guarnicao-tipo': 'ameaca', 'x-guarnicao-arquivo': '<b>$(rm -rf ~)</b>', urgency: 2});
    assert.deepEqual(d, {tipo: 'ameaca', arquivo: '<b>$(rm -rf ~)</b>'});
    assert.equal(lerDados({urgency: 1}), null);
});

test('o detalhe pula a linha do nome do arquivo', () => {
    assert.equal(detalhe({arquivo: 'x.exe'}, 'x.exe\nEICAR\nbaixado agora'), 'EICAR · baixado agora');
    assert.equal(detalhe({}, '305 arquivos, tudo limpo'), '305 arquivos, tudo limpo');
});

test('Trancar só com caminho e hash', () => {
    const com = botoes({tipo: 'ameaca', caminho: '/a/x.exe', sha256: 'ab'});
    assert.deepEqual(com.map(b => b.rotulo), ['Abrir painel', 'Trancar']);
    assert.deepEqual(com[1].args, ['quarentena', 'trancar', '/a/x.exe', '--sha256', 'ab']);
    assert.deepEqual(botoes({tipo: 'ameaca'}).map(b => b.rotulo), ['Abrir painel']);
    assert.deepEqual(botoes({tipo: 'trancado', quarentena: 'id1'})[0].args, ['quarentena', 'restaurar', 'id1']);
    assert.deepEqual(botoes({tipo: 'limpa'}), []);
});

test('toda ação do escudo tem rótulo e comando', () => {
    for (const acao of ['varrer', 'abrir', 'trancar', 'atualizar', 'parar']) {
        assert.ok(ROTULOS_MENU[acao] && COMANDOS_MENU[acao], acao);
    }
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_arte_extensao.py` e `node --test extensao/testes/`
Expected: FAIL (módulos não existem).

- [ ] **Step 3: Implement**

`extensao/construir_arte.py`:

```python
"""Gera a arte da extensão a partir dos desenhos aprovados.

Rode de novo se os retratos (guarnicao/launcher/estatico/arte) ou o escudo
(design/telas/barra-v2.html) mudarem: python3 extensao/construir_arte.py
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARTE_PAINEL = RAIZ / "guarnicao" / "launcher" / "estatico" / "arte"
BARRA = RAIZ / "design" / "telas" / "barra-v2.html"
DESTINO = RAIZ / "extensao" / "guarnicao@eduardomilani8.github.io" / "arte"
NS = 'xmlns="http://www.w3.org/2000/svg"'
# A barra do GNOME é sempre escura e o texto dela é branco. Não usamos ícone
# "symbolic": o GNOME recolore preenchendo os traços, e o escudo vazado viraria
# um escudo cheio.
COR_DA_BARRA = "#ffffff"


def _interior(svg: str) -> str:
    return re.sub(r"^\s*<svg[^>]*>|</svg>\s*$", "", svg.strip())


def retrato(nome: str) -> str:
    """O retrato com as definições comuns (moldura etc.) dentro, para abrir sozinho."""
    proprio = (ARTE_PAINEL / f"{nome}.svg").read_text(encoding="utf-8").strip()
    abertura = re.match(r"<svg[^>]*>", proprio).group(0)
    viewbox = re.search(r'viewBox="([^"]+)"', abertura).group(1)
    comum = _interior((ARTE_PAINEL / "comum.svg").read_text(encoding="utf-8"))
    return (f'<svg {NS} xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="{viewbox}" '
            f'width="240" height="300">{comum}{proprio[len(abertura):]}')


def escudos() -> dict[str, str]:
    html = BARRA.read_text(encoding="utf-8")

    def pega(padrao: str) -> str:
        return re.search(padrao, html, flags=re.S).group(0)

    mascara = pega(r'<mask id="brMx".*?</mask>')
    simbolo = {i: re.sub(r"^<symbol[^>]*>|</symbol>$", "", pega(rf'<symbol id="{i}"[^>]*>.*?</symbol>'))
               for i in ("brOk", "brVar", "brAtn", "brAmc")}

    def svg(corpo: str, extra: str = "") -> str:
        return (f'<svg {NS} width="16" height="16" viewBox="0 0 16 16"><defs>{mascara}{extra}</defs>'
                f"{corpo}</svg>").replace("currentColor", COR_DA_BARRA)

    saida = {"escudo-certo": svg(simbolo["brOk"]), "escudo-atencao": svg(simbolo["brAtn"]),
             "escudo-ameaca": svg(simbolo["brAmc"])}
    for nivel in range(1, 5):
        # O escudo vai de y 2,5 a 14,5; enche de baixo para cima, em 4 passos.
        topo = 14.5 - 12 * nivel / 4
        recorte = f'<clipPath id="brMeio"><rect x="0" y="{topo:.2f}" width="16" height="16"/></clipPath>'
        saida[f"escudo-procurando-{nivel}"] = svg(simbolo["brVar"], recorte)
    return saida


def ameia(largura: int = 426) -> str:
    """A faixa de ameias do alto do aviso (avisos-v3): dentes de 18 px a cada 30 px."""
    dentes = "".join(f'<rect x="{x}" y="0" width="18" height="8" fill="#3a4258"/>' for x in range(6, largura, 30))
    return (f'<svg {NS} width="{largura}" height="16" viewBox="0 0 {largura} 16">'
            f'<rect x="0" y="7" width="{largura}" height="9" fill="#3a4258"/>{dentes}'
            f'<rect x="0" y="7" width="{largura}" height="1" fill="#5a6584"/></svg>')


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome in ("cavaleiro", "arqueira", "vidente", "carcereiro"):
        (DESTINO / f"{nome}.svg").write_text(retrato(nome), encoding="utf-8")
    for nome, svg in escudos().items():
        (DESTINO / f"{nome}.svg").write_text(svg, encoding="utf-8")
    (DESTINO / "ameia.svg").write_text(ameia(), encoding="utf-8")
    print(f"Arte gerada em {DESTINO}")


if __name__ == "__main__":
    main()
```

`extensao/guarnicao@eduardomilani8.github.io/metadata.json`:

```json
{
  "uuid": "guarnicao@eduardomilani8.github.io",
  "name": "Guarnição",
  "description": "O escudo da Guarnição na barra e os avisos com a arte da muralha.",
  "shell-version": ["50"],
  "url": "https://github.com/EduardoMilani8/guarnicao"
}
```

`extensao/guarnicao@eduardomilani8.github.io/regras.js` (sem nenhum `gi://`, para rodar no Node):

```js
// Regras puras dos avisos e do escudo: sem GNOME aqui, para testar com node --test.

export const NOMES = {cavaleiro: 'Cavaleiro', arqueira: 'Arqueira', vidente: 'Vidente', carcereiro: 'Carcereiro'};

// Cor do estado no cartão (avisos-v3): perigo = vermelho, atenção = âmbar, o resto sem faixa colorida.
export const TOM = {ameaca: 'perigo', varias: 'perigo', bloqueado: 'perigo', suspeito: 'atencao', bases: 'atencao'};

export const FRASE = {
    ameaca: 'O Carcereiro aguarda sua ordem.',
    varias: 'O Carcereiro aguarda sua ordem.',
    suspeito: 'O Vidente percebeu algo estranho.',
    bloqueado: 'O protetor impediu que ele rodasse.',
    bases: 'Sem bases novas, o Cavaleiro não reconhece ameaças recentes.',
};

export const ROTULOS_MENU = {
    varrer: 'Varredura rápida', abrir: 'Abrir painel', trancar: 'Abrir painel e trancar',
    atualizar: 'Atualizar agora', parar: 'Parar varredura',
};

export const COMANDOS_MENU = {
    varrer: ['varrer', '--rapida', '--agendada'], abrir: ['launcher'], trancar: ['launcher'],
    atualizar: ['atualizar'], parar: ['varrer', '--parar'],
};

// Só os hints x-guarnicao-*, e só se forem texto. Nada é interpretado.
export function lerDados(hints) {
    const dados = {};
    for (const [chave, valor] of Object.entries(hints ?? {})) {
        if (chave.startsWith('x-guarnicao-') && typeof valor === 'string')
            dados[chave.slice('x-guarnicao-'.length)] = valor;
    }
    return dados.tipo ? dados : null;
}

// Quando há arquivo, a primeira linha do corpo é o nome dele: o cartão já mostra em fonte mono.
export function detalhe(dados, corpo) {
    const linhas = (corpo ?? '').split('\n').map(l => l.trim()).filter(Boolean);
    return (dados.arquivo ? linhas.slice(1) : linhas).join(' · ');
}

// Os botões de cada aviso, na ordem do avisos-v3 (o dourado por último).
export function botoes(dados) {
    const painel = rotulo => ({rotulo, args: ['launcher']});
    const trancar = dados.caminho && dados.sha256
        ? [{rotulo: 'Trancar', args: ['quarentena', 'trancar', dados.caminho, '--sha256', dados.sha256], principal: true}]
        : [];
    switch (dados.tipo) {
    case 'ameaca': return [painel('Abrir painel'), ...trancar];
    case 'suspeito': return [painel('Ver detalhes'), ...trancar];
    case 'varias': return [painel('Ver o que foi achado'), {rotulo: 'Trancar todas', args: ['launcher'], principal: true}];
    case 'bases': return [painel('Abrir painel'), {rotulo: 'Atualizar agora', args: ['atualizar'], principal: true}];
    case 'bloqueado': return [painel('Abrir painel')];
    case 'trancado': return dados.quarentena ? [{rotulo: 'Desfazer', args: ['quarentena', 'restaurar', dados.quarentena]}] : [];
    default: return [];
    }
}
```

Crie `extensao/package.json` com `{"type": "module", "private": true}` para o Node tratar os `.js` como módulos.

Rode `python3 extensao/construir_arte.py` para gerar a pasta `arte/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/test_arte_extensao.py && node --test extensao/testes/`
Expected: PASS nos dois.

- [ ] **Step 5: Commit**

```bash
git add extensao/ tests/test_arte_extensao.py
git commit -m "Extensão: esqueleto, arte gerada dos desenhos aprovados e regras dos avisos"
```

---

### Task 9: Escudo na barra

**Files:**
- Create: `extensao/guarnicao@eduardomilani8.github.io/extension.js`
- Create: `extensao/guarnicao@eduardomilani8.github.io/comandos.js`
- Create: `extensao/guarnicao@eduardomilani8.github.io/escudo.js`
- Create: `extensao/guarnicao@eduardomilani8.github.io/stylesheet.css`

**Interfaces:**
- Consumes: `guarnicao estado --json` (Task 6), `progresso.json` (Task 4), `ROTULOS_MENU`/`COMANDOS_MENU` (Task 8), `config.json` gravado pelo instalador (Task 11): `{"python": "<.venv/bin/python>", "pasta": "<raiz do repo>"}`.
- Produces: `class Comandos { constructor(pastaDaExtensao); rodar(args: string[]); async json(args: string[]) }`; `Escudo` (GObject, `PanelMenu.Button`) com `atualizar()`.

- [ ] **Step 1: Implement** `comandos.js`

```js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

Gio._promisify(Gio.Subprocess.prototype, 'communicate_utf8_async');

// Roda "python -m guarnicao ..." a partir da pasta do projeto. O instalador grava
// config.json ao lado da extensão dizendo onde ela está.
export class Comandos {
    constructor(pastaDaExtensao) {
        const [, bytes] = GLib.file_get_contents(GLib.build_filenamev([pastaDaExtensao, 'config.json']));
        const config = JSON.parse(new TextDecoder().decode(bytes));
        this._python = config.python;
        this._pasta = config.pasta;
    }

    // Lista de argumentos, nunca shell: um nome de arquivo malicioso continua texto.
    _iniciar(args, flags) {
        const lancador = new Gio.SubprocessLauncher({flags});
        lancador.set_cwd(this._pasta);
        return lancador.spawnv([this._python, '-m', 'guarnicao', ...args]);
    }

    rodar(args) {
        try {
            this._iniciar(args, Gio.SubprocessFlags.NONE);
        } catch (e) {
            logError(e, 'Guarnição: não deu para rodar o comando');
        }
    }

    async json(args) {
        const processo = this._iniciar(args, Gio.SubprocessFlags.STDOUT_PIPE);
        const [saida] = await processo.communicate_utf8_async(null, null);
        return JSON.parse(saida);
    }
}
```

- [ ] **Step 2: Implement** `escudo.js`

```js
import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {ROTULOS_MENU, COMANDOS_MENU} from './regras.js';

// O escudo da barra (barra-v2): o estado se lê pela forma, a cor só aparece no menu.
export const Escudo = GObject.registerClass(
class Escudo extends PanelMenu.Button {
    _init(pasta, comandos) {
        super._init(0.5, 'Guarnição');
        this._pasta = pasta;
        this._comandos = comandos;
        this._icone = new St.Icon({style_class: 'system-status-icon'});
        this.add_child(this._icone);
        this._mostrar({estado: 'certo', titulo: 'Guarnição', linhas: ['Conferindo…'], acoes: []});

        this._relogio = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            this.atualizar();
            return GLib.SOURCE_CONTINUE;
        });
        const andamento = Gio.File.new_for_path(
            GLib.build_filenamev([GLib.get_user_cache_dir(), 'guarnicao', 'progresso.json']));
        this._vigia = andamento.monitor_file(Gio.FileMonitorFlags.NONE, null);
        this._vigia.connect('changed', () => this.atualizar());
        this.atualizar();
    }

    async atualizar() {
        if (this._ocupado)
            return;
        this._ocupado = true;
        try {
            this._mostrar(await this._comandos.json(['estado', '--json']));
        } catch (e) {
            logError(e, 'Guarnição: não deu para ler o estado');
        } finally {
            this._ocupado = false;
        }
    }

    _mostrar(e) {
        const nome = e.estado === 'procurando' ? `escudo-procurando-${e.nivel ?? 1}` : `escudo-${e.estado}`;
        this._icone.gicon = Gio.FileIcon.new(Gio.File.new_for_path(`${this._pasta}/arte/${nome}.svg`));

        this.menu.removeAll();
        const titulo = new PopupMenu.PopupMenuItem(e.titulo, {reactive: false});
        titulo.add_style_class_name(`guarnicao-menu-titulo ${e.estado}`);
        this.menu.addMenuItem(titulo);
        for (const linha of e.linhas ?? []) {
            const item = new PopupMenu.PopupMenuItem(linha, {reactive: false});
            item.add_style_class_name('guarnicao-menu-linha');
            this.menu.addMenuItem(item);
        }
        if (!e.acoes?.length)
            return;
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        e.acoes.forEach((acao, i) => {
            const item = new PopupMenu.PopupMenuItem(ROTULOS_MENU[acao] ?? acao);
            // Com problema, a ação que resolve vem primeiro e dourada (barra-v2).
            if (i === 0 && e.estado !== 'certo')
                item.add_style_class_name('guarnicao-acao-principal');
            item.connect('activate', () => this._comandos.rodar(COMANDOS_MENU[acao]));
            this.menu.addMenuItem(item);
        });
    }

    destroy() {
        GLib.source_remove(this._relogio);
        this._vigia.cancel();
        super.destroy();
    }
});
```

- [ ] **Step 3: Implement** `extension.js` (os avisos entram na Task 10)

```js
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {Comandos} from './comandos.js';
import {Escudo} from './escudo.js';

export default class Guarnicao extends Extension {
    enable() {
        this._comandos = new Comandos(this.path);
        this._escudo = new Escudo(this.path, this._comandos);
        Main.panel.addToStatusArea(this.uuid, this._escudo);
    }

    disable() {
        this._escudo?.destroy();
        this._escudo = null;
        this._comandos = null;
    }
}
```

- [ ] **Step 4: Implement** `stylesheet.css` (parte do menu; a do cartão entra na Task 10)

```css
/* Menu do escudo (barra-v2). A cor do estado só aparece aqui, junto do texto. */
.guarnicao-menu-titulo { font-family: Fraunces, serif; font-weight: 600; font-size: 15px; color: #F3EEE2; }
.guarnicao-menu-titulo.ameaca { color: #FF8A7A; }
.guarnicao-menu-titulo.atencao { color: #F0B65A; }
.guarnicao-menu-linha { font-size: 13px; color: #B7BCCB; }
.guarnicao-acao-principal { color: #D4AF6A; font-weight: 700; }
```

- [ ] **Step 5: Check syntax**

Run: `for f in extensao/guarnicao@eduardomilani8.github.io/*.js; do node --check "$f" || exit 1; done`
Expected: sem erros (o Node só confere a sintaxe; os `gi://` só existem dentro do GNOME). O teste de verdade é na Task 12.

- [ ] **Step 6: Commit**

```bash
git add extensao/
git commit -m "Extensão: escudo na barra com o menu da barra-v2"
```

---

### Task 10: Avisos com a arte da muralha

**Files:**
- Create: `extensao/guarnicao@eduardomilani8.github.io/cartao.js`
- Create: `extensao/guarnicao@eduardomilani8.github.io/avisos.js`
- Modify: `extensao/guarnicao@eduardomilani8.github.io/extension.js`, `stylesheet.css`

**Interfaces:**
- Consumes: `lerDados`, `detalhe`, `botoes`, `TOM`, `FRASE`, `NOMES` (Task 8); `Comandos.rodar` (Task 9); `Escudo.atualizar` (Task 9).
- Produces: `cartao({dados, titulo, corpo, pastaArte, aoClicar}) -> St.Widget`; `class Avisos { constructor(pastaArte, comandos, aoChegar); ligar() -> boolean; desligar() }`.

- [ ] **Step 1: Implement** `cartao.js`

```js
import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {NOMES, TOM, FRASE, botoes, detalhe} from './regras.js';

const VERTICAL = Clutter.Orientation.VERTICAL;

// O cartão do avisos-v3: ameias no alto, faixa da cor do estado, retrato com a
// luz da tocha, textos e botões. Tudo texto puro (St.Label), nunca markup.
export function cartao({dados, titulo, corpo, pastaArte, aoClicar}) {
    const tom = TOM[dados.tipo] ?? '';
    const caixa = new St.BoxLayout({style_class: 'guarnicao-cartao', orientation: VERTICAL});
    caixa.add_child(new St.Widget({style_class: 'guarnicao-ameia'}));

    const miolo = new St.BoxLayout({style_class: `guarnicao-corpo ${tom}`, orientation: VERTICAL});
    caixa.add_child(miolo);
    const linha = new St.BoxLayout({style_class: 'guarnicao-linha'});
    miolo.add_child(linha);

    if (NOMES[dados.personagem]) {
        const luz = new St.Bin({style_class: `guarnicao-luz ${tom}`});
        luz.set_child(new St.Widget({
            style_class: 'guarnicao-retrato',
            style: `background-image: url("file://${pastaArte}/${dados.personagem}.svg");`,
        }));
        linha.add_child(luz);
    }

    const textos = new St.BoxLayout({style_class: 'guarnicao-textos', orientation: VERTICAL, x_expand: true});
    linha.add_child(textos);
    const rotulo = (texto, classe) => {
        const l = new St.Label({text: texto, style_class: classe});
        l.clutter_text.line_wrap = true;
        l.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        textos.add_child(l);
    };
    rotulo('GUARNIÇÃO · AGORA', 'guarnicao-quem');
    rotulo(titulo, `guarnicao-titulo ${tom}`);
    if (dados.arquivo)
        rotulo(dados.arquivo, 'guarnicao-arquivo');
    const texto = detalhe(dados, corpo);
    if (texto)
        rotulo(texto, 'guarnicao-detalhe');
    if (FRASE[dados.tipo])
        rotulo(FRASE[dados.tipo], 'guarnicao-frase');

    const lista = botoes(dados);
    if (lista.length) {
        const fila = new St.BoxLayout({style_class: 'guarnicao-botoes', x_align: Clutter.ActorAlign.END});
        for (const b of lista) {
            const botao = new St.Button({
                label: b.rotulo, can_focus: true,
                style_class: `guarnicao-botao${b.principal ? ' principal' : ''}`,
            });
            botao.connect('clicked', () => aoClicar(b.args));
            fila.add_child(botao);
        }
        miolo.add_child(fila);
    }
    return caixa;
}
```

- [ ] **Step 2: Implement** `avisos.js`

```js
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {cartao} from './cartao.js';
import {lerDados} from './regras.js';

const APP = 'Guarnição';
const chave = (titulo, corpo) => `${titulo}\n${corpo}`;

// Os avisos chegam pelo notify-send como sempre. Aqui guardamos os dados
// escondidos (hints x-guarnicao-*) e, quando o GNOME monta o balão, trocamos o
// recheio pelo cartão da muralha. Posição, tempo e foco continuam com o GNOME.
export class Avisos {
    constructor(pastaArte, comandos, aoChegar) {
        this._pastaArte = pastaArte;
        this._comandos = comandos;
        this._aoChegar = aoChegar;
        this._dados = new Map();
    }

    ligar() {
        const daemon = Main.notificationDaemon?._fdoNotificationDaemon;
        const tray = Main.messageTray;
        // Plano B: se o GNOME mudou por dentro, não mexemos nos avisos (ficam os comuns).
        if (typeof daemon?.NotifyAsync !== 'function' || typeof tray?._showNotification !== 'function') {
            console.warn('Guarnição: esta versão do GNOME não deixa trocar o desenho dos avisos');
            return false;
        }
        const avisos = this;
        this._daemon = daemon;
        this._tray = tray;
        this._notifyOriginal = daemon.NotifyAsync;
        this._mostrarOriginal = tray._showNotification;
        daemon.NotifyAsync = function (params, invocation) {
            try {
                avisos._guardar(params);
            } catch (e) {
                logError(e, 'Guarnição: não deu para ler o aviso');
            }
            return avisos._notifyOriginal.call(this, params, invocation);
        };
        tray._showNotification = function () {
            avisos._mostrarOriginal.call(this);
            try {
                avisos._vestir(this);
            } catch (e) {
                logError(e, 'Guarnição: não deu para desenhar o cartão');   // fica o balão comum
            }
        };
        return true;
    }

    desligar() {
        if (!this._daemon)
            return;
        this._daemon.NotifyAsync = this._notifyOriginal;
        this._tray._showNotification = this._mostrarOriginal;
        this._tray.bannerAlignment = Clutter.ActorAlign.CENTER;
        this._daemon = this._tray = null;
        this._dados.clear();
    }

    _guardar(params) {
        const [app, , , titulo, corpo, , hints] = params;
        if (app !== APP)
            return;
        const simples = {};
        for (const [k, v] of Object.entries(hints ?? {}))
            simples[k] = typeof v?.deepUnpack === 'function' ? v.deepUnpack() : v;
        this._aoChegar();
        const dados = lerDados(simples);
        if (!dados)
            return;
        this._dados.set(chave(titulo, corpo), dados);
        if (this._dados.size > 20)
            this._dados.delete(this._dados.keys().next().value);
    }

    _vestir(tray) {
        const n = tray._notification;
        const k = n ? chave(n.title, n.body ?? '') : null;
        const dados = k ? this._dados.get(k) : null;
        // Os da Guarnição aparecem no canto superior direito (avisos-v3); os outros, no meio.
        tray.bannerAlignment = dados ? Clutter.ActorAlign.END : Clutter.ActorAlign.CENTER;
        if (!dados)
            return;
        this._dados.delete(k);
        const banner = tray._banner;
        banner.set_child(cartao({
            dados, titulo: n.title, corpo: n.body ?? '', pastaArte: this._pastaArte,
            aoClicar: args => {
                this._comandos.rodar(args);
                n.destroy();
            },
        }));
        banner.style_class = 'guarnicao-banner';
    }
}
```

- [ ] **Step 3: Wire it** em `extension.js`

Acrescente `import {Avisos} from './avisos.js';`; no fim de `enable()`:

```js
        this._avisos = new Avisos(`${this.path}/arte`, this._comandos, () => this._escudo?.atualizar());
        this._avisos.ligar();
```

e no começo de `disable()`:

```js
        this._avisos?.desligar();
        this._avisos = null;
```

- [ ] **Step 4: Add the card styles** ao fim de `stylesheet.css` (valores do avisos-v3)

```css
/* Cartão dos avisos (avisos-v3, muralha). */
.guarnicao-banner { background: none; border: none; box-shadow: none; padding: 0; margin: 0 14px; }
.guarnicao-cartao {
  width: 420px; border: 3px solid #4a536b; border-top-width: 0; border-radius: 0 0 8px 8px;
  background-gradient-direction: vertical; background-gradient-start: #0a1328; background-gradient-end: #14203A;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
}
.guarnicao-ameia { height: 16px; background-image: url("arte/ameia.svg"); background-size: cover; }
.guarnicao-corpo { border-top: 3px solid #4a536b; padding: 14px 16px 16px; spacing: 12px; }
.guarnicao-corpo.perigo { border-top-color: #FF8A7A; }
.guarnicao-corpo.atencao { border-top-color: #F0B65A; }
.guarnicao-linha { spacing: 14px; }
.guarnicao-luz {
  width: 92px; height: 108px; border-radius: 46px; margin: -14px;
  background-gradient-direction: radial; background-gradient-start: rgba(255, 190, 120, 0.22);
  background-gradient-end: rgba(0, 0, 0, 0);
}
.guarnicao-luz.perigo { background-gradient-start: rgba(255, 120, 80, 0.35); }
.guarnicao-luz.atencao { background-gradient-start: rgba(255, 190, 100, 0.32); }
.guarnicao-retrato { width: 64px; height: 80px; background-size: contain; }
.guarnicao-textos { spacing: 3px; }
.guarnicao-quem { font-family: "Source Sans 3", sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 1px; color: #E3C384; }
.guarnicao-titulo { font-family: Fraunces, serif; font-size: 19px; font-weight: 600; color: #F3EEE2; }
.guarnicao-titulo.perigo { color: #FF8A7A; }
.guarnicao-titulo.atencao { color: #F0B65A; }
.guarnicao-arquivo { font-family: "Source Code Pro", monospace; font-size: 14px; color: #F3EEE2; }
.guarnicao-detalhe { font-family: "Source Sans 3", sans-serif; font-size: 14px; color: #B7BCCB; }
.guarnicao-frase { font-family: Fraunces, serif; font-style: italic; font-size: 15px; color: #B7BCCB; }
.guarnicao-botoes { spacing: 8px; }
.guarnicao-botao {
  min-height: 40px; padding: 0 14px; border-radius: 8px; border: 1px solid #6a7aa0;
  background-color: rgba(10, 16, 32, 0.75); color: #F3EEE2;
  font-family: "Source Sans 3", sans-serif; font-size: 15px; font-weight: 600;
}
.guarnicao-botao:hover, .guarnicao-botao:focus { background-color: rgba(40, 52, 84, 0.9); }
.guarnicao-botao.principal { border-width: 0; padding: 0 18px; background-color: #D4AF6A; color: #0D1626; font-weight: 700; }
.guarnicao-botao.principal:hover, .guarnicao-botao.principal:focus { background-color: #E3C384; }
```

- [ ] **Step 5: Check syntax**

Run: `for f in extensao/guarnicao@eduardomilani8.github.io/*.js; do node --check "$f" || exit 1; done && node --test extensao/testes/`
Expected: sem erros; testes das regras continuam passando.

- [ ] **Step 6: Commit**

```bash
git add extensao/
git commit -m "Extensão: avisos com o cartão da muralha, no canto, com plano B"
```

---

### Task 11: Instalador e documentação

**Files:**
- Create: `contrib/instalar-extensao.sh`
- Modify: `README.md`, `CONTRIBUTING.md`, `ROADMAP.md`

**Interfaces:**
- Produces: `config.json` na pasta instalada da extensão (`{"python", "pasta"}`, Task 9); fontes em `~/.local/share/fonts/guarnicao/`.

- [ ] **Step 1: Implement** `contrib/instalar-extensao.sh` (e `chmod +x`)

```bash
#!/usr/bin/env bash
# Instala a extensão do GNOME da Guarnição para o seu usuário (sem sudo):
# o escudo na barra e os avisos com a arte da muralha.
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
uuid="guarnicao@eduardomilani8.github.io"
destino="$HOME/.local/share/gnome-shell/extensions/$uuid"
fontes="$HOME/.local/share/fonts/guarnicao"

if [ ! -x "$raiz/.venv/bin/python" ]; then
  echo "Não achei $raiz/.venv/bin/python. Instale a Guarnição primeiro (veja o README)." >&2
  exit 1
fi

rm -rf "$destino"
mkdir -p "$destino" "$fontes"
cp -r "$raiz/extensao/$uuid/." "$destino/"
# Onde a Guarnição está, para os botões rodarem "python -m guarnicao ...".
"$raiz/.venv/bin/python" -c 'import json, sys; print(json.dumps({"python": sys.argv[1], "pasta": sys.argv[2]}))' \
  "$raiz/.venv/bin/python" "$raiz" > "$destino/config.json"

cp "$raiz"/guarnicao/launcher/estatico/fontes/*.woff2 "$fontes/"
fc-cache -f "$fontes" >/dev/null 2>&1 || true

if gnome-extensions enable "$uuid" 2>/dev/null; then
  echo "Extensão ligada."
else
  echo "Para ligar depois de entrar de novo: gnome-extensions enable $uuid"
fi
echo "No Wayland, saia e entre de novo na sessão para o GNOME carregar a extensão."
```

- [ ] **Step 2: Run it once, without a new session**

Run: `bash -n contrib/instalar-extensao.sh && contrib/instalar-extensao.sh && cat ~/.local/share/gnome-shell/extensions/guarnicao@eduardomilani8.github.io/config.json`
Expected: sem erro de sintaxe; `config.json` com os caminhos de `~/guarnicao`.

- [ ] **Step 3: Docs**

- `README.md`: seção "Extensão do GNOME" com o que ela faz (escudo e avisos), o comando `contrib/instalar-extensao.sh`, o aviso de sair e entrar no Wayland, e que sem ela os avisos continuam os comuns.
- `CONTRIBUTING.md`: como testar a extensão (`node --test extensao/testes/`, `python3 extensao/construir_arte.py`, e o GNOME de teste da Task 12).
- `ROADMAP.md`: marcar `[x]` "Varredura automática que terminou limpa" e "Extensão do GNOME com a mesma arte do painel", e o item pai "Avisos que mostram que a Guarnição está trabalhando".

- [ ] **Step 4: Commit**

```bash
git add contrib/instalar-extensao.sh README.md CONTRIBUTING.md ROADMAP.md
git commit -m "Extensão: instalador e documentação"
```

---

### Task 12: Teste ao vivo

**Files:** nenhum novo (só correções que aparecerem, cada uma com o próprio commit).

- [ ] **Step 1: GNOME de teste em janela**

O usuário instala uma vez: `sudo apt install mutter-dev-bin`. Depois:

```bash
dbus-run-session -- bash -c '
  gnome-shell --devkit --wayland &
  sleep 10
  gnome-extensions enable guarnicao@eduardomilani8.github.io
  sleep 3
  cd ~/guarnicao
  .venv/bin/python -c "
import sys; sys.path.insert(0, \".\")
from guarnicao import notificacao as n
n.notificar(\"Ameaça encontrada\", \"fatura-novembro.pdf.exe\nEICAR · reconhecida pelo Cavaleiro\", urgente=True,
            dados={\"tipo\": \"ameaca\", \"personagem\": \"cavaleiro\", \"arquivo\": \"fatura-novembro.pdf.exe\"})
"
  wait'
```

Expected: na janela do GNOME de teste, o escudo aparece na barra e o cartão de ameaça aparece no canto superior direito, como no avisos-v3.

- [ ] **Step 2: Cada tipo e cada estado**

Dentro da mesma sessão de teste, dispare um aviso de cada tipo (`ameaca`, `varias`, `suspeito`, `bases`, `limpa`, `trancado`, `bloqueado`) e force os estados do escudo (uma varredura rodando = procurando; `chmod` numa base para envelhecê-la ou um `historico.jsonl` de teste com um achado = ameaça). Tire uma foto de cada (`gdbus call --session --dest org.gnome.Shell.Screenshot --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false /tmp/claude-.../tipo.png`) e compare com `avisos-v3-muralha.html` e `barra-v2.html`. Diferenças que não derem para resolver no St: mostrar ao usuário antes de seguir.

- [ ] **Step 3: Botões**

Clique em cada botão no GNOME de teste e confira o efeito (painel abre; Trancar tranca e mostra "Trancado na quarentena" com Desfazer; Desfazer devolve; Atualizar agora roda `atualizar`; Parar varredura para a do terminal).

- [ ] **Step 4: Plano B**

Desligue a troca do desenho (no GNOME de teste, `gnome-extensions disable` e `enable` de novo, depois um aviso com a extensão desligada) e confira que o aviso comum aparece com o mesmo texto.

- [ ] **Step 5: Na sessão do usuário**

`contrib/instalar-extensao.sh`, o usuário sai e entra de novo, e repetimos os Steps 2-3 de verdade, com a confirmação dele na tela.

- [ ] **Step 6: Suíte completa**

Run: `.venv/bin/pytest -q && node --test extensao/testes/`
Expected: tudo passa.
