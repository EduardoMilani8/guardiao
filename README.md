# Guardião

Antivírus de estudo para Linux, escrito em Python. Ele detecta ameaças em camadas
(assinaturas, regras YARA e heurísticas), varre o computador inteiro ou só os locais
de risco, isola arquivos em quarentena, vigia a pasta de Downloads em tempo real e
audita projetos de programação atrás de riscos na cadeia de pacotes (npm, PyPI).

> ⚠️ É um projeto de aprendizado: **não substitui um antivírus de verdade**. Para
> proteção real no Linux, use o [ClamAV](https://www.clamav.net/) e bons hábitos
> (ler scripts antes de rodar, desconfiar de `curl | sh`).

## O que ele faz

| Camada | Como detecta | Exemplo |
|---|---|---|
| **Assinaturas** | SHA-256 do arquivo contra um banco de hashes conhecidos | Arquivo de teste EICAR |
| **Regras YARA** | Padrões dentro dos arquivos ([YARA-X](https://virustotal.github.io/yara-x/)) | Shell reverso, minerador de criptomoeda, script baixado e executado direto |
| **Heurísticas** | Sinais combinados numa pontuação de 0 a 100 | Executável disfarçado de `.jpg`, extensão dupla, entropia alta |
| **Varredura** | Rápida, completa ou de uma pasta, em vários processos e com cache | 1 milhão de arquivos em ~3,5 min; a segunda vez pula o que não mudou |
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
# Varredura rápida: Downloads, /tmp, autostart, cron, serviços do systemd...
.venv/bin/python -m guardiao varrer --rapida

# Varredura completa: todo o disco (com sudo, inclui os arquivos do sistema)
.venv/bin/python -m guardiao varrer --completa
sudo .venv/bin/python -m guardiao varrer --completa

# Varrer uma pasta ou arquivo (e isolar ameaças)
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

### Varredura

A completa percorre só sistemas de arquivos com arquivos de verdade (ext4, btrfs,
vfat...), pelo tipo listado em `/proc/self/mounts`. Ficam de fora `/proc`, `/sys`,
snaps somente leitura e discos de rede; discos externos entram com
`--incluir-externos`. Links simbólicos não são seguidos.

Arquivos limpos entram num cache (`~/.cache/guardiao`) e são pulados na próxima vez,
a menos que mudem (tamanho, mtime ou ctime) ou que as regras sejam atualizadas.
Ameaças e suspeitos nunca entram no cache. `--sem-cache` reanalisa tudo.

Exclusões e limite de tamanho ficam em `~/.config/guardiao/config.toml`:

```toml
excluir_pastas = ["~/Vídeos", "~/VirtualBox VMs"]
excluir_padroes = ["*.iso"]
tamanho_maximo_mb = 512     # padrão: 256
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

Os botões disparam a varredura **rápida**, a **completa** ou a de uma pasta escolhida
num seletor nativo, e dá para **parar** no meio. **Simular ataque** cria amostras
inofensivas numa pasta temporária para mostrar cada guardião em ação. O launcher
nunca roda como root; para os arquivos do sistema, use `sudo` na linha de comando.

## Estrutura

```
guardiao/
  scanner.py       aplica as camadas a um arquivo (hash → YARA → heurísticas)
  varredura.py     modos rápida/completa, exclusões e análise em paralelo
  cache.py         lembra dos arquivos limpos que não mudaram
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

## Licença

[MIT](LICENSE) © 2026 Eduardo Milani
