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
| **Assinaturas** | SHA-256 do arquivo contra um banco de hashes conhecidos, incluindo os do [MalwareBazaar](https://bazaar.abuse.ch) | Arquivo de teste EICAR, malware real enviado por pesquisadores |
| **ClamAV** | Milhões de assinaturas do [ClamAV](https://www.clamav.net/), mantidas pelo freshclam | Trojans, worms e ransomware conhecidos |
| **Regras YARA** | Padrões dentro dos arquivos ([YARA-X](https://virustotal.github.io/yara-x/)): as nossas e ~5 mil do [YARA Forge](https://github.com/YARAHQ/yara-forge) | Shell reverso, minerador de criptomoeda, famílias de malware conhecidas |
| **Pacotes** | Olha dentro de `.zip` e `.tar` (e `.docx`, `.jar`...), com proteção contra zip bomb | Malware zipado, macro dentro de documento |
| **Heurísticas** | Sinais combinados numa pontuação de 0 a 100 | Executável disfarçado de `.jpg`, extensão dupla, entropia alta |
| **Varredura** | Rápida, completa ou de uma pasta, em vários processos e com cache | 1 milhão de arquivos em ~8 min; a segunda vez pula o que não mudou |
| **Atualização** | Bases baixadas de hora em hora, com troca atômica | Download quebrado nunca deixa o Guardião sem a base anterior |
| **Quarentena** | Move para `~/.local/share/guardiao/quarentena` sem permissão de execução | Reversível com `quarentena restaurar` |
| **Monitor** | inotify (via watchdog) na pasta Downloads | Analisa cada download assim que termina |
| **Caçador** | Procura o que já se instalou: bibliotecas injetadas, processos estranhos, persistência fora dos pacotes, binários alterados | Rootkit no `/etc/ld.so.preload`, minerador rodando de `/dev/shm`, serviço que voltou depois do reboot |
| **Módulo de dev** | Audita um projeto | `postinstall` malicioso, typosquatting (`reqeusts`), `.vscode/tasks.json` com `runOn: folderOpen` |

## Instalação

```bash
git clone https://github.com/EduardoMilani8/guardiao.git
cd guardiao
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Requer Python 3.11+. Para a camada do ClamAV (recomendada):

```bash
sudo apt install clamav clamav-daemon
```

Cada camada é opcional: sem o `yara-x` ou sem o ClamAV, ela é desativada (com aviso)
e o resto continua funcionando.

### Bases de detecção

```bash
.venv/bin/python -m guardiao atualizar            # baixa o que estiver desatualizado
.venv/bin/python -m guardiao atualizar --status   # situação de cada base
```

Para atualizar sozinho de hora em hora, há um timer de usuário do systemd em
[`contrib/guardiao-atualizar.timer`](contrib/guardiao-atualizar.timer), com a
instalação no próprio arquivo. A varredura e o launcher avisam quando uma base passa
de 2 dias sem atualizar.

O MalwareBazaar precisa de uma chave gratuita, criada em
[auth.abuse.ch](https://auth.abuse.ch). Coloque no `~/.config/guardiao/config.toml`:

```toml
[malwarebazaar]
chave = "..."
```

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

# Caçar persistência e rootkits já instalados (com sudo, vê todos os processos)
.venv/bin/python -m guardiao cacar
sudo .venv/bin/python -m guardiao cacar --todos

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

### Caçador

A varredura procura arquivos ruins; o `cacar` pergunta se alguma coisa já se
instalou e está se escondendo. O critério central é *veio de um pacote?*: tudo o
que o apt instalou está registrado em `/var/lib/dpkg/info`, e o resto é listado e
passa pelas mesmas camadas da varredura.

| Onde olha | Alto risco quando |
|---|---|
| `/etc/ld.so.preload` e `LD_PRELOAD` dos processos | a biblioteca não veio de um pacote ou está numa pasta temporária |
| `/proc/<pid>/exe` | o processo roda de `/tmp`, `/var/tmp`, `/dev/shm` ou da memória (`memfd`), ou o scanner reconhece o executável, que continua legível mesmo apagado do disco |
| systemd, cron, autostart e `/etc/rc.local` | o comando roda algo de uma pasta temporária, ou o YARA ou o scanner condenam o comando, o script ou o programa chamado |
| `dpkg --verify` | um executável ou biblioteca do sistema não é mais o que o pacote instalou |

Ficam como **atenção** um executável apagado que sumiu de vez e uma unidade do
systemd que sobrepõe a de um pacote trocando o comando (o truque de sequestrar o
`sshd.service`). Unidades do snap e mascaradas são ignoradas; o que não veio de
pacote mas não tem nada de estranho aparece como informativo, com `--todos`.
O `dpkg --verify` leva uns 30 segundos (`--sem-pacotes` pula esse passo). Sem
root, só os seus processos e os arquivos legíveis por você são conferidos.

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
  cacador.py       caça persistência e rootkits (preload, processos, systemd, cron, dpkg)
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
