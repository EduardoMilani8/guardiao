# Como cada parte funciona

O [README](../README.md) resume o Guardião. Aqui estão os detalhes de cada parte,
para quem quer entender as decisões ou ajustar o comportamento.

- [Protetor](#protetor)
- [Monitor de downloads](#monitor-de-downloads)
- [Monitor de comportamento](#monitor-de-comportamento)
- [Atualização das bases](#atualização-das-bases)
- [Varreduras](#varreduras)
- [VirusTotal](#virustotal)
- [Painel](#painel)
- [Caçador](#caçador)
- [Auditoria de projetos](#auditoria-de-projetos)

## Protetor

Com o `fanotify` (`FAN_OPEN_EXEC_PERM`), o kernel segura cada `execve()` até o
Guardião responder. Se o arquivo é uma ameaça (hash conhecido, ClamAV ou regra YARA
de gravidade alta), quem tentou executar recebe "Operação não permitida" e uma
notificação aparece na sua área de trabalho.

```bash
sudo contrib/instalar-protetor.sh          # instala ou atualiza o serviço
journalctl -u guardiao-protetor -f         # o que ele está bloqueando
```

O instalador copia o Guardião para `/opt/guardiao`, de root. Um serviço root
rodando código que a sua conta pode alterar seria um atalho para root para qualquer
malware que entrasse nela. Por isso, depois de um `git pull`, rode o instalador de
novo.

O cuidado principal é nunca travar o computador:

- **Prazo de 2 segundos.** Se a análise demorar mais (um binário de 300 MB leva
  cerca de 3,5 s no YARA), a execução é liberada. Se depois der ameaça, você é
  avisado com o comando para encerrá-la, e da próxima vez ela já é bloqueada.
- **Fail-open.** Se o protetor cair, o kernel libera tudo que estava esperando.
- **Programas do sistema passam direto** (`/usr`, `/bin`, `/lib`, de root e sem
  escrita para outros usuários). O resto é analisado uma vez e lembrado por 1 hora
  ou até o arquivo mudar. Custo medido: 0,1 ms a mais por execução.
- **Malware que se apaga depois de executar** continua sendo analisado, pelo
  descritor que o kernel entrega.
- As análises rodam em processos separados: o YARA-X segura o GIL do Python e,
  numa thread, congelaria o relógio do prazo.

Limite: vale para o que é *executado*. `python script.py` executa o Python, que é
confiável, e não o script. Scripts com `#!` e permissão de execução, e binários,
passam pelo protetor. Para testar sem bloquear nada:
`sudo .venv/bin/python -m guardiao proteger --so-avisar`.

## Monitor de downloads

O serviço `guardiao-monitor` observa a pasta Downloads com o inotify. Cada arquivo
é analisado assim que o navegador termina de baixá-lo (arquivos `.part` e
`.crdownload` são ignorados até virarem o nome final) e, se for uma ameaça, vai
direto para a quarentena. Para vigiar outras pastas:
`.venv/bin/python -m guardiao monitorar ~/Downloads ~/Área\ de\ Trabalho --isolar`.

## Monitor de comportamento

Assinaturas e regras olham o arquivo, e malware novo muda o arquivo o tempo todo.
O que ele *faz* muda bem menos. O monitor lê o `/proc` a cada 5 segundos (cerca de
0,7% de um núcleo) e avisa quando encontra:

- **Shell reverso:** um shell ou interpretador (`bash`, `python`, `nc`...) com a
  entrada e a saída ligadas a uma conexão TCP, ou um shell aberto pelo `socat` ou
  `nc` com uma conexão ativa. Quem está do outro lado digita comandos como você.
- **Minerador:** um processo usando mais de meio núcleo e conectado a uma porta
  típica de pool de mineração (3333, 4444, 14444...).

Conexões dentro da própria máquina (127.0.0.1) pedem só atenção. O alerta traz o
pid e o comando para encerrar; o Guardião não mata processos sozinho. Sem root, só
os seus processos são vistos, que é onde roda o que você baixa. Para desligar:
`monitorar --sem-comportamento`.

## Atualização das bases

| Base | O que traz | Frequência |
|---|---|---|
| [MalwareBazaar](https://bazaar.abuse.ch) | Hashes de malware enviado por pesquisadores | De hora em hora |
| [YARA Forge](https://github.com/YARAHQ/yara-forge) | Cerca de 5 mil regras da comunidade, calibradas contra falsos positivos | Uma vez por semana |
| [ClamAV](https://www.clamav.net/) | Milhões de assinaturas, atualizadas pelo próprio `freshclam` | Pelo ClamAV |

O timer `guardiao-atualizar` confere de hora em hora; quando nada mudou, leva
segundos. A troca é atômica: um download quebrado nunca deixa o Guardião sem a
versão anterior. A varredura e o painel avisam quando uma base passa de 2 dias sem
atualizar.

```bash
.venv/bin/python -m guardiao atualizar            # atualiza agora
.venv/bin/python -m guardiao atualizar --status   # situação de cada base
```

O MalwareBazaar precisa de uma chave gratuita, criada em
[auth.abuse.ch](https://auth.abuse.ch), no `~/.config/guardiao/config.toml`:

```toml
[malwarebazaar]
chave = "..."
```

## Varreduras

- **Rápida:** Downloads, área de trabalho, `/tmp`, `/var/tmp`, `/dev/shm`,
  `~/.local/bin`, programas que iniciam com a sessão, serviços do systemd e cron.
- **Completa:** todos os sistemas de arquivos com arquivos de verdade (ext4, btrfs,
  vfat...). Ficam de fora `/proc`, `/sys`, snaps somente leitura e discos de rede;
  discos externos entram com `--incluir-externos`. Links simbólicos não são seguidos.

A análise roda em paralelo. Arquivos limpos entram num cache e são pulados na
próxima vez, a menos que mudem (tamanho, mtime ou ctime) ou que as regras sejam
atualizadas. Quando chegam hashes novos, o cache reconfere o hash guardado de cada
arquivo sem precisar lê-lo de novo. Ameaças e suspeitos nunca entram no cache.

Exclusões e limite de tamanho ficam no `~/.config/guardiao/config.toml`:

```toml
excluir_pastas = ["~/Vídeos", "~/VirtualBox VMs"]
excluir_padroes = ["*.iso"]
tamanho_maximo_mb = 512     # padrão: 256
```

**Agendadas.** Os timers `guardiao-varrer-rapida` (todo dia, por volta das 12:30) e
`guardiao-varrer-completa` (domingo, por volta das 13:00, só com o carregador
ligado) rodam em prioridade mínima de CPU e disco, com no máximo 4 processos. Se o
computador estava desligado na hora, rodam assim que ele ligar. Elas **não isolam
sozinhas**: notificam o que acharem, e você decide no painel. Um alarme falso numa
varredura do disco inteiro moveria um arquivo seu sem você ver.

**Histórico.** Toda varredura (do terminal, agendada ou do painel) grava quando foi,
quanto levou e o que achou em `~/.local/share/guardiao/historico.jsonl`.
`guardiao historico --achados` mostra as últimas.

## VirusTotal

Opcional e desligado por padrão. Com uma chave grátis, criada em
[virustotal.com](https://www.virustotal.com), no `~/.config/guardiao/config.toml`:

```toml
[virustotal]
chave = "..."
```

o Guardião pergunta ao VirusTotal o que uns 70 antivírus acham de um arquivo. Só
o SHA-256 sai do computador, nunca o conteúdo. Ainda assim, cada consulta conta ao
VirusTotal que aquele hash existe na sua máquina, então ela é feita só em três
casos:

- **downloads novos**, pelo monitor (reinicie o serviço depois de pôr a chave:
  `systemctl --user restart guardiao-monitor`);
- **arquivos suspeitos** encontrados pela varredura, no máximo 20 por varredura;
- quando você pede: `guardiao virustotal <arquivo>`.

| Antivírus que apontam "malicioso" | Resultado |
|---|---|
| 5 ou mais | ameaça (e vai para a quarentena se o monitor estiver com `--isolar`) |
| 2 a 4 | suspeito |
| 1 | só uma observação: um antivírus sozinho costuma ser alarme falso |

A chave grátis permite 4 consultas por minuto e 500 por dia. As respostas ficam
guardadas (arquivos conhecidos por 7 dias, desconhecidos por 1 dia) e a cota é
contada num arquivo com trava, que o monitor e as varreduras dividem. Passado o
limite por minuto, o Guardião espera a vaga; acabada a cota do dia, ele avisa e
segue sem o VirusTotal. O protetor não consulta: ele tem 2 segundos para decidir,
e a rede não cabe nesse prazo.

## Painel

Uma página local (`guardiao launcher`, em `127.0.0.1`) em que cada personagem
representa uma camada do motor:

| Personagem | Camada |
|---|---|
| O Guardião | Assinaturas: hashes e ClamAV |
| A Arqueira | Regras YARA |
| O Vidente | Heurísticas |
| O Carcereiro | Quarentena |

Dá para disparar a varredura rápida, a completa ou a de uma pasta, e parar no meio.
**Simular ataque** cria amostras inofensivas numa pasta temporária para mostrar
cada camada em ação. Ao abrir, o painel mostra quando foram as últimas varreduras
e as ameaças que elas acharam e que continuam no lugar.

Cada ameaça tem um botão **Trancar** (e **Trancar todas**, quando há várias). A
página nunca diz ao servidor *qual caminho* mover: ela manda um código que o próprio
servidor deu à ameaça, e o arquivo só vai para a quarentena se ainda for exatamente
o que foi analisado (mesmo SHA-256). Um site aberto no navegador não tem como pedir
"mova /tal/arquivo". O painel nunca roda como root.

## Caçador

A varredura procura arquivos ruins; o `cacar` procura o que já se instalou e está
se escondendo. O critério central é: *veio de um pacote?* Tudo o que o apt instalou
está registrado em `/var/lib/dpkg/info`; o resto é listado e passa pelas mesmas
camadas da varredura.

| Onde olha | Alto risco quando |
|---|---|
| `/etc/ld.so.preload` e `LD_PRELOAD` dos processos | a biblioteca não veio de um pacote ou está numa pasta temporária |
| `/proc/<pid>/exe` | o processo roda de `/tmp`, `/dev/shm` ou da memória, ou o executável é reconhecido como ameaça (mesmo apagado do disco) |
| systemd, cron, autostart e `/etc/rc.local` | o comando roda algo de uma pasta temporária, ou o comando ou o programa chamado são condenados |
| `dpkg --verify` | um executável ou biblioteca do sistema não é mais o que o pacote instalou |
| `.bashrc`, `.zshrc`, `/etc/profile.d` | põem uma pasta temporária no `PATH` ou rodam algo de `/tmp`; um alias que troca o `sudo` pede atenção |
| `~/.ssh/authorized_keys` | a chave tem a marca de uma botnet; chaves acrescentadas nos últimos 7 dias pedem atenção |

O caçador também dá uma olhada de 3 segundos no comportamento dos processos. O
`dpkg --verify` leva uns 30 segundos (`--sem-pacotes` pula esse passo). Sem root,
só os seus processos e os arquivos legíveis por você são conferidos.

```bash
.venv/bin/python -m guardiao cacar
sudo .venv/bin/python -m guardiao cacar --todos
```

## Auditoria de projetos

`guardiao dev <pasta>` procura riscos num projeto de programação antes de você
instalar as dependências ou abri-lo no editor:

- scripts de instalação do npm (`postinstall`) que baixam e executam código;
- nomes de pacotes parecidos com os populares (typosquatting, como `reqeusts`);
- tarefas do VS Code que rodam sozinhas ao abrir a pasta (`runOn: folderOpen`);
- hooks do git com comandos suspeitos.
