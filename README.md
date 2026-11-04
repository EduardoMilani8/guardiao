# Guardião

Antivírus para Linux, escrito em Python. Ele detecta ameaças em camadas (hashes do
MalwareBazaar, ClamAV, regras YARA e heurísticas) com bases atualizadas de hora em
hora, varre o computador inteiro ou só os locais de risco, caça persistência e
rootkits já instalados, isola arquivos em quarentena, vigia a pasta de Downloads em
tempo real e audita projetos de programação atrás de riscos na cadeia de pacotes.

> 📊 **Medido com 195 amostras reais** do MalwareBazaar (novembro de 2026): pega
> **99,5%** do malware já reportado e **cerca de metade** do malware Linux novo, que
> ninguém reportou ainda. Ainda não analisa comportamento nem bloqueia um arquivo
> antes de ele ser aberto; veja [Taxa de detecção](#taxa-de-detecção) e o
> [roadmap](ROADMAP.md). Bons hábitos continuam valendo: ler scripts antes de rodar
> e desconfiar de `curl | sh`.

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
| **Comportamento** | O que os processos fazem, lido do `/proc` a cada 5 s pelo monitor | Shell reverso (`bash` falando com a rede), minerador (CPU alta conectado a um pool) |
| **Caçador** | Procura o que já se instalou: bibliotecas injetadas, processos estranhos, persistência fora dos pacotes, binários alterados | Rootkit no `/etc/ld.so.preload`, minerador rodando de `/dev/shm`, serviço que voltou depois do reboot |
| **Módulo de dev** | Audita um projeto | `postinstall` malicioso, typosquatting (`reqeusts`), `.vscode/tasks.json` com `runOn: folderOpen` |

## Taxa de detecção

Medida em 4 de novembro de 2026 com 195 amostras enviadas ao
[MalwareBazaar](https://bazaar.abuse.ch) entre 2 e 4 de novembro: 98 programas
Linux (ELF), 48 programas Windows (EXE), 24 scripts shell e 25 JavaScript. As
amostras foram só lidas, nunca executadas, e apagadas depois.

**Malware já reportado: 99,5%** (194 de 195). Os hashes do MalwareBazaar são
baixados de hora em hora; uma amostra enviada por pesquisadores passa a ser
reconhecida em até uma hora.

**Malware novo**, medido *sem* a base de hashes (que daria 100% por construção,
porque as amostras vieram dela):

| | Todas | Linux (ELF) | Windows (EXE) | Shell | JavaScript |
|---|---|---|---|---|---|
| ClamAV sozinho | 22,1% | 39,8% | 8,3% | 0% | 0% |
| Regras YARA sozinhas | 3,6% | 5,1% | 0% | 8,3% | 0% |
| **Guardião: ameaça** | **25,6%** | **44,9%** | 8,3% | 8,3% | 0% |
| **Guardião: ameaça ou suspeito** | **34,9%** | **54,1%** | 16,7% | 29,2% | 0% |

O que mais escapou foram variantes recompiladas da botnet Mirai, cada uma com um
hash novo, e JavaScript ofuscado (ladrões de senha do Windows).

Depois disso vieram regras para os droppers JavaScript do Windows Script Host
(`regras/javascript_windows.yar`). Escritas olhando 58 amostras e medidas em
outras **41 que não foram usadas para escrevê-las**: o JavaScript foi de 0% para
**46,3%**, sem nenhum falso positivo em 1,14 milhão de arquivos do disco. Detectar malware
recém-criado só pelo conteúdo é difícil para qualquer antivírus; os comerciais
compensam com análise de comportamento, que é a [Fase 4](ROADMAP.md). O caçador
não entra nesta conta: ele procura o que já está rodando ou instalado.

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
| `.bashrc`, `.zshrc`, `/etc/profile.d`... (e o que eles carregam com `source`) | põem uma pasta temporária no `PATH` ou rodam algo de `/tmp`; um alias ou função que troca o `sudo` pede atenção |
| `~/.ssh/authorized_keys` | a chave tem a marca de uma botnet (Outlaw); chaves acrescentadas nos últimos 7 dias pedem atenção |

Ficam como **atenção** um executável apagado que sumiu de vez e uma unidade do
systemd que sobrepõe a de um pacote trocando o comando (o truque de sequestrar o
`sshd.service`). Unidades do snap e mascaradas são ignoradas; o que não veio de
pacote mas não tem nada de estranho aparece como informativo, com `--todos`.
O `dpkg --verify` leva uns 30 segundos (`--sem-pacotes` pula esse passo). Sem
root, só os seus processos e os arquivos legíveis por você são conferidos.

### Comportamento

Assinaturas e regras olham o arquivo, e malware novo muda o arquivo o tempo
todo; o que ele *faz* muda bem menos. O monitor olha os processos a cada 5
segundos (uns 0,7% de um núcleo) e notifica quando encontra:

- **Shell reverso**: um shell ou interpretador (`bash`, `python`, `nc`...) com a
  entrada e a saída ligadas a uma conexão TCP, ou um shell aberto pelo `socat`/`nc`
  com uma conexão (a variante com terminal falso). Quem está do outro lado digita
  comandos como você.
- **Minerador**: um processo usando mais de meio núcleo e conectado a uma porta
  típica de pool de mineração (3333, 4444, 14444...).

Conexões dentro da própria máquina (127.0.0.1) pedem só atenção. O alerta traz o
pid e o comando para encerrar; o Guardião não mata processos sozinho. Sem root,
só os seus processos são vistos, que é onde roda o que você baixa. O `cacar`
também dá uma olhada de 3 segundos. Para desligar no monitor: `--sem-comportamento`.

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
  comportamento.py shells reversos e mineradores em execução, pelo /proc
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
