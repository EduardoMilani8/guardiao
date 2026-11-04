# Roadmap

Plano para o Guardião se aproximar de um antivírus completo, baseado no que os
antivírus populares (Bitdefender, Norton, ESET, Microsoft Defender, Sophos, ClamAV)
oferecem hoje e no que de fato ataca Linux (mineradores via SSH, botnets, rootkits
eBPF, ataques à cadeia de pacotes).

## Fase 1: varredura completa

- [x] Modos **rápida** (onde malware costuma ficar), **completa** (todo o disco) e
      **personalizada** (pasta escolhida num seletor nativo)
- [x] Ignorar o que não é arquivo de verdade (`/proc`, `/sys`, `/dev`) pelo tipo do
      sistema de arquivos, e discos externos e de rede por padrão
- [x] Exclusões configuráveis e limite de tamanho (`~/.config/guardiao/config.toml`)
- [x] Cache: pular arquivos que não mudaram desde a última varredura
- [x] Análise em paralelo, um processo por núcleo
- [x] Modo root opcional para as pastas do sistema
- [x] Launcher com os novos modos e botão de parar

## Fase 2: banco de detecção de verdade

- [x] ClamAV como camada extra
- [x] Hashes do MalwareBazaar
- [x] Regras YARA da comunidade (YARA Forge), calibradas contra falsos positivos
- [x] Varredura dentro de `.zip` e `.tar`, com proteção contra zip bombs
- [x] Comando `atualizar` e atualização automática de hora em hora
- [x] Medir a taxa de detecção com amostras reais do MalwareBazaar (99,5% do já reportado,
      cerca de metade do malware Linux novo; veja o README)
- [ ] Medir de novo de tempos em tempos, e incluir JavaScript ofuscado nas regras
- [ ] Opcional: consultar o hash (nunca o arquivo) no VirusTotal

## Fase 3: caçador de persistência e rootkits

- [x] Entradas em `/etc/ld.so.preload` e `LD_PRELOAD` em processos
- [x] Serviços systemd, cron e autostart que não vieram de pacotes
- [x] Processos rodando de `/tmp` e `/dev/shm` ou com executável apagado
- [x] Binários do sistema alterados (`dpkg --verify`)
- [ ] Linhas suspeitas em `~/.bashrc`, `~/.profile` e afins (alias de `sudo`, `curl | sh`)
- [ ] Chaves SSH autorizadas que não deveriam estar lá (`~/.ssh/authorized_keys`)
- [ ] Rodar o caçador como root e calibrar de novo

## Fase 4: proteção em tempo real de verdade

- [ ] On-access com `fanotify` (o kernel espera o veredito antes de abrir o arquivo),
      com limite de tempo e liberando o arquivo em caso de falha
- [ ] Monitor de comportamento leve: mineradores e shells reversos em execução

## Fase 5: rotina e painel

- [ ] Varredura rápida diária e completa semanal (systemd timer)
- [ ] Histórico de varreduras
- [ ] Carcereiro isolando ameaças com um clique no launcher

## Fora do escopo

VPN, backup na nuvem, monitoramento da dark web, controle de dispositivos e
isolamento de rede: são outros produtos ou recursos corporativos.
