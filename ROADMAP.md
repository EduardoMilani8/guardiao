# Roadmap

O plano foi montado comparando o que os antivírus populares (Bitdefender, Norton,
ESET, Microsoft Defender, Sophos, ClamAV) oferecem com o que de fato ataca Linux
(mineradores via SSH, botnets, rootkits eBPF, ataques à cadeia de pacotes). As cinco
fases estão concluídas; os itens em aberto estão em [Próximos passos](#próximos-passos).

## Fase 1: varredura completa

- [x] Modos **rápida** (onde malware costuma ficar), **completa** (todo o disco) e
      **personalizada** (pasta escolhida num seletor nativo)
- [x] Ignorar o que não é arquivo de verdade (`/proc`, `/sys`, `/dev`) pelo tipo do
      sistema de arquivos, e discos externos e de rede por padrão
- [x] Exclusões configuráveis e limite de tamanho (`~/.config/guardiao/config.toml`)
- [x] Cache: pular arquivos que não mudaram desde a última varredura
- [x] Análise em paralelo, um processo por núcleo
- [x] Modo root opcional para as pastas do sistema
- [x] Painel com os novos modos e botão de parar

## Fase 2: banco de detecção de verdade

- [x] ClamAV como camada extra
- [x] Hashes do MalwareBazaar
- [x] Regras YARA da comunidade (YARA Forge), calibradas contra falsos positivos
- [x] Varredura dentro de `.zip` e `.tar`, com proteção contra zip bombs
- [x] Comando `atualizar` e atualização automática de hora em hora
- [x] Medir a taxa de detecção com amostras reais do MalwareBazaar (99,5% do já reportado,
      cerca de metade do malware Linux novo; veja [docs/deteccao.md](docs/deteccao.md))
- [x] Regras para JavaScript ofuscado do Windows Script Host (0% → 46,3% em amostras novas)

## Fase 3: caçador de persistência e rootkits

- [x] Entradas em `/etc/ld.so.preload` e `LD_PRELOAD` em processos
- [x] Serviços systemd, cron e autostart que não vieram de pacotes
- [x] Processos rodando de `/tmp` e `/dev/shm` ou com executável apagado
- [x] Binários do sistema alterados (`dpkg --verify`)
- [x] Linhas suspeitas em `~/.bashrc`, `~/.profile` e afins (alias de `sudo`, `curl | sh`)
- [x] Chaves SSH autorizadas que não deveriam estar lá (`~/.ssh/authorized_keys`)
- [x] Rodar o caçador como root e calibrar de novo

## Fase 4: proteção em tempo real de verdade

- [x] On-access com `fanotify` (o kernel espera o veredito antes de executar o arquivo),
      com limite de tempo e liberando o arquivo em caso de falha
- [x] Monitor de comportamento leve: mineradores e shells reversos em execução

## Fase 5: rotina e painel

- [x] Varredura rápida diária e completa semanal (systemd timer)
- [x] Histórico de varreduras
- [x] Carcereiro isolando ameaças com um clique no painel

## Próximos passos

- [ ] Medir a taxa de detecção de novo de tempos em tempos, com amostras recentes
      (`ferramentas/medir_deteccao.py`; a próxima a partir de 11/11/2026)
- [x] Opcional: consultar o hash (nunca o arquivo) no VirusTotal
- [ ] **Painel novo**: um visual mais bonito para o painel, que vai servir de base
      para a arte dos avisos
- [ ] **Avisos que mostram que o Guardião está trabalhando, sem cansar.** O objetivo é a
      pessoa lembrar que está protegida sem ser incomodada:
  - [x] Ameaça: aviso forte, que fica até a pessoa agir
  - [ ] Varredura automática que terminou limpa: resumo discreto, que some sozinho
        (no máximo um por dia)
  - [x] Downloads limpos: sem aviso (já é assim)
  - [ ] Extensão do GNOME com a mesma arte do painel: o aviso no canto da tela e um
        escudo na barra de cima que mostra o estado (no Wayland, um aplicativo comum
        não pode escolher onde a janela aparece)
- [ ] **Desempenho em segundo plano**: medir com calma e reduzir o que der. Medido em
      04/11/2026: protetor e monitor somam cerca de 400 MB de memória e menos de 1% de
      um núcleo; as regras YARA são carregadas duas vezes (no monitor e no protetor)

## Para depois

Já dá para fazer, mas fica de fora por enquanto. Entra se alguém pedir ou se fizer
falta no uso.

- [ ] **Modo claro**: as telas no tema claro já estão desenhadas (painel nos quatro
      estados, histórico, quarentena, avisos e escudo da barra), mas o painel novo vai
      ser lançado só no escuro.
- [ ] **Celular**: por enquanto a Guarnição é só para o PC. Primeiro ela precisa estar
      funcionando bem e bem testada no computador. Antes de qualquer coisa no celular,
      falta decidir como as pessoas iriam instalar (APK, loja ou outro jeito).

## Fora do escopo

VPN, backup na nuvem, monitoramento da dark web, controle de dispositivos e
isolamento de rede: são outros produtos ou recursos corporativos.
