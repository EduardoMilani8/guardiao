# Guardião

Antivírus de estudo para Linux, escrito em Python. Ele detecta ameaças em camadas
(assinaturas, regras YARA e heurísticas), isola arquivos em quarentena, vigia a pasta
de Downloads em tempo real e audita projetos de programação atrás de riscos na cadeia
de pacotes (npm, PyPI).

> ⚠️ É um projeto de aprendizado: **não substitui um antivírus de verdade**. Para
> proteção real no Linux, use o [ClamAV](https://www.clamav.net/) e bons hábitos
> (ler scripts antes de rodar, desconfiar de `curl | sh`).

## O que ele faz

| Camada | Como detecta | Exemplo |
|---|---|---|
| **Assinaturas** | SHA-256 do arquivo contra um banco de hashes conhecidos | Arquivo de teste EICAR |
| **Regras YARA** | Padrões dentro dos arquivos ([YARA-X](https://virustotal.github.io/yara-x/)) | Shell reverso, minerador de criptomoeda, script baixado e executado direto |
| **Heurísticas** | Sinais combinados numa pontuação de 0 a 100 | Executável disfarçado de `.jpg`, extensão dupla, entropia alta |
| **Quarentena** | Move para `~/.local/share/guardiao/quarentena` sem permissão de execução | Reversível com `quarentena restaurar` |
| **Monitor** | inotify (via watchdog) na pasta Downloads | Analisa cada download assim que termina |
| **Módulo de dev** | Audita um projeto | `postinstall` malicioso, typosquatting (`reqeusts`), `.vscode/tasks.json` com `runOn: folderOpen` |

## Instalação

```bash
git clone https://github.com/EduardoMilani8/guardiao.git
cd guardiao
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Requer Python 3.11+. Sem o `yara-x` instalado, a camada de regras é desativada e o
resto continua funcionando.

## Uso

```bash
# Varrer uma pasta (e isolar ameaças)
.venv/bin/python -m guardiao varrer ~/Downloads --isolar

# Vigiar Downloads em tempo real, com notificações na área de trabalho
.venv/bin/python -m guardiao monitorar --isolar

# Auditar um projeto de programação
.venv/bin/python -m guardiao dev ~/meu-projeto

# Gerenciar a quarentena
.venv/bin/python -m guardiao quarentena listar
.venv/bin/python -m guardiao quarentena restaurar <id>

# Protótipo do launcher com os guardiões (abre no navegador)
.venv/bin/python -m guardiao launcher
```

### Monitor como serviço

Para o monitor iniciar junto com a sessão, há um serviço de usuário do systemd em
[`contrib/guardiao-monitor.service`](contrib/guardiao-monitor.service), com as
instruções de instalação no próprio arquivo.

## Launcher (protótipo)

Uma página local onde cada guardião representa uma camada do motor e reage quando
ela encontra algo:

- 🛡️ **O Guardião**: assinaturas (reconhece ameaças conhecidas)
- 🏹 **A Arqueira**: regras YARA (mira em padrões perigosos)
- 🔮 **O Vidente**: heurísticas (sente o que não tem nome)
- ⛓️ **O Carcereiro**: quarentena (tranca o que é perigoso)

O botão **Simular ataque** cria amostras inofensivas numa pasta temporária para
mostrar cada um em ação.

## Estrutura

```
guardiao/
  scanner.py       percorre arquivos e aplica as camadas (hash → YARA → heurísticas)
  assinaturas.py   banco de hashes (assinaturas/hashes.txt)
  regras_yara.py   carrega e aplica as regras de regras/
  heuristicas.py   sinais e pontuação de suspeita
  quarentena.py    isola e restaura arquivos
  monitor.py       vigia pastas em tempo real
  dev.py           auditoria de projetos (npm, PyPI, VS Code, hooks do git)
  eventos.py       converte resultados em eventos JSON para interfaces
  launcher/        protótipo da interface com os guardiões
regras/            regras YARA (regras/dev/ só para o módulo de dev)
dados/             listas de pacotes populares para detectar typosquatting
tests/             testes (pytest)
```

## Testes

```bash
.venv/bin/python -m pytest -q
```

Os testes usam apenas amostras inofensivas (o arquivo de teste EICAR e trechos de
script montados em tempo de execução, para o próprio código não ser detectado).
