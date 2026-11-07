# Extensão do GNOME: escudo na barra e avisos na muralha

Data: 07/11/2026 · Estado: aprovado em conversa, aguardando revisão deste documento

## Objetivo

A Guarnição precisa lembrar que existe e está trabalhando, sem cansar ("se notifica
demais, o cara desliga"). Hoje os avisos são os balões comuns do GNOME, e não há nada
na tela quando está tudo bem. A extensão traz:

1. um **escudo na barra de cima** que mostra o estado o tempo todo, com um menu;
2. os **avisos com a arte da muralha**, no canto superior direito, com botões.

Referências visuais fixas (aprovadas pelo usuário):
`design/telas/barra-v2.html` (escudo e menu) e `design/telas/avisos-v3-muralha.html`
(avisos). Só tema escuro. Ambiente: GNOME Shell 50, Wayland.

Critério de sucesso: com a extensão ligada, cada tipo de aviso aparece como no
avisos-v3, os botões funcionam, e o escudo mostra os quatro estados como na barra-v2.
Sem a extensão (ou se o GNOME mudar por dentro), tudo continua funcionando como
hoje, com os avisos comuns.

## Caminho escolhido (A)

Os avisos continuam indo pelo `notify-send` (D-Bus), que já funciona de todos os
lugares, inclusive do protetor que roda como root (`setpriv` para a sessão do
usuário). Cada aviso leva dados escondidos (*hints*). A extensão reconhece os avisos
da Guarnição e só troca o desenho. Um caminho só: a extensão é a "pele" por cima.

Descartados: canal próprio por arquivo (o protetor escreveria na pasta do usuário, e
cada serviço teria que saber se a extensão está ligada) e serviço D-Bus próprio
(muito mais código, e o protetor ainda precisaria chegar à sessão).

## Peças

### 1. Avisos com dados escondidos (`guarnicao/notificacao.py`)

`comando()` ganha um parâmetro `dados: dict | None`. Cada chave vira um hint
`--hint=string:x-guarnicao-<chave>:<valor>`. Chaves:

| hint | valores | para quê |
|---|---|---|
| `x-guarnicao-tipo` | `ameaca`, `varias`, `suspeito`, `bases`, `limpa`, `trancado`, `bloqueado` | qual cartão do avisos-v3 desenhar |
| `x-guarnicao-personagem` | `cavaleiro`, `arqueira`, `vidente`, `carcereiro`, vazio | o retrato (vazio no aviso limpo) |
| `x-guarnicao-arquivo` | nome do arquivo | linha em fonte mono |
| `x-guarnicao-caminho` | caminho completo | para o botão Trancar |
| `x-guarnicao-sha256` | hash | Trancar só tranca se o arquivo ainda é o mesmo |
| `x-guarnicao-quarentena` | id na quarentena | para o botão Desfazer |

`bloqueado` (o protetor impediu um arquivo de executar) não tem quadro próprio no
avisos-v3: usa o cartão de ameaça, com a frase "O protetor impediu que ele rodasse"
e só o botão Abrir painel (já está resolvido, não há o que trancar).

O título e o corpo continuam como hoje: quem não tem a extensão lê o mesmo texto.
Os valores vão como argumentos separados (nunca shell), como já é feito.

Quem chama `notificar()` passa os dados: varredura agendada (`__main__.cmd_varrer`),
monitor (download isolado → `trancado`; suspeito → `suspeito`), comportamento
(`suspeito`, Vidente), protetor (`bloqueado`, Cavaleiro/Arqueira conforme a camada),
bases paradas (`bases`, Cavaleiro) e o resumo limpo (`limpa`).

Regra do avisos-v3 mantida pelo GNOME: avisos de ameaça são `critical` e ficam até a
pessoa agir; o limpo e o trancado somem sozinhos. Vários achados de uma vez viram um
aviso só (`varias`), como já é na varredura agendada.

### 2. `guarnicao estado --json` (comando novo)

Imprime um JSON com o que o escudo e o menu mostram:

```json
{"estado": "certo | procurando | atencao | ameaca",
 "titulo": "Você está protegido", "linhas": ["Última: rápida · hoje, 12:30", "..."],
 "progresso": {"feitos": 183, "total": 305} ,
 "acoes": ["varrer", "abrir"]}
```

Reaproveita `launcher/estado.montar()` (serviços, bases, próximas varreduras), o
histórico (achados pendentes = ameaça; última varredura) e o arquivo de andamento.
Ordem de prioridade: ameaça pendente > procurando > atenção (bases velhas, freshclam
ou protetor/monitor parados) > certo. Os textos seguem a barra-v2.

### 3. Arquivo de andamento da varredura

`varredura.executar()` grava `~/.cache/guarnicao/progresso.json`
(`{"pid", "tipo", "feitos", "total", "inicio"}`) no máximo a cada 1 s e apaga ao
terminar (inclusive se for interrompida). O escudo enche de baixo para cima em
poucos passos, sem animar (barra-v2). "Parar varredura" manda SIGTERM para o `pid`,
só se ele ainda for um processo `guarnicao varrer` do mesmo usuário.

### 4. `guarnicao quarentena trancar <caminho> --sha256 <hash>` (comando novo)

O que o botão Trancar chama. Mesma regra do botão do painel
(`launcher/servidor.isolar`): só tranca se o arquivo ainda existe, não é link e tem
o mesmo hash; o motivo e a camada vêm do achado no histórico; marca o achado como
isolado. A lógica sai do servidor para uma função comum, usada pelos dois.
Arquivo do sistema (sem permissão): não tranca e o aviso diz para abrir o painel.

### 5. A extensão (`extensao/guarnicao@eduardomilani8.github.io/`)

- `metadata.json` (shell-version `["50"]`), `extension.js`, `stylesheet.css`,
  `arte/` (retratos aprovados, moldura da muralha e os 4 escudos em SVG) e
  `fontes/` (Fraunces e Source Sans 3, as mesmas do painel).
- **Escudo** (`PanelMenu.Button`): ícone simbólico de 16 px na cor do texto do
  GNOME, vazado com visto / enchendo / vazado com exclamação / cheio com x. Menu como
  na barra-v2: título, linhas, e o botão dourado da ação certa primeiro quando há
  problema. Atualiza a cada 60 s, quando chega um aviso da Guarnição e quando o
  arquivo de andamento muda (`Gio.FileMonitor`).
- **Avisos:** a extensão envolve `NotifyAsync` do daemon de notificações do GNOME
  para guardar os hints `x-guarnicao-*` dos avisos cujo app é "Guarnição", e envolve
  `MessageTray._showNotification`: quando o balão é da Guarnição, troca o conteúdo
  pelo cartão do avisos-v3 (céu noturno, borda de pedra, ameias, faixa da cor do
  estado, retrato com luz de tocha, título, arquivo, frase do personagem e botões) e
  move o balão para o canto superior direito enquanto ele está na tela. Desliza uma
  vez ao aparecer; nada pisca, sem som.
- **Botões** rodam `python -m guarnicao ...` com `Gio.Subprocess` (lista de
  argumentos, nunca shell), a partir de `~/guarnicao`:

| botão | comando |
|---|---|
| Abrir painel / Ver detalhes / Ver o que foi achado | `launcher` |
| Trancar | `quarentena trancar <caminho> --sha256 <hash>` |
| Trancar todas | abre o painel (decisão de várias de uma vez fica no painel) |
| Desfazer | `quarentena restaurar <id>` |
| Atualizar agora | `atualizar` |
| Varredura rápida | `varrer --rapida --agendada` |
| Parar varredura | SIGTERM no `pid` do andamento (ver peça 3) |

- **Plano B:** se `Main.notificationDaemon._fdoNotificationDaemon.NotifyAsync` ou
  `Main.messageTray._showNotification` não existirem, a extensão não mexe nos avisos
  (ficam os comuns) e o escudo funciona normalmente. Qualquer erro ao desenhar um
  cartão também cai no balão comum. Ao desligar a extensão, tudo é devolvido.

### 6. Instalação (`contrib/instalar-extensao.sh`)

Copia a extensão para `~/.local/share/gnome-shell/extensions/`, as fontes para
`~/.local/share/fonts/guarnicao/` (convertidas para TTF se o FreeType não ler WOFF2)
e roda `gnome-extensions enable`. No Wayland, a primeira vez exige sair e entrar na
sessão. README e CONTRIBUTING ganham a seção da extensão.

## Testes

- **pytest (Python):** hints no comando do `notify-send` (e que valores maliciosos
  continuam texto); cada quem-chama passa o tipo certo; `estado --json` nos quatro
  estados e na prioridade entre eles; arquivo de andamento criado, atualizado e
  apagado (inclusive se a varredura for interrompida); `quarentena trancar` tranca,
  recusa arquivo mudado, link e arquivo sumido.
- **Extensão, ao vivo:** primeiro num GNOME de teste em janela (`gnome-shell
  --devkit --wayland`, precisa do pacote `mutter-dev-bin`, que o usuário instala com
  sudo), sem mexer na sessão dele. Lá disparo cada tipo de aviso e cada estado do
  escudo e comparo a foto com os desenhos. Depois instalo na sessão dele (sair e
  entrar uma vez) e confiro de novo. Também confiro o plano B desligando a troca do
  desenho.

## Fora do escopo

Modo claro, tela de bloqueio, sons, tela de configurações da extensão, outras
versões do GNOME além da 50, publicar no extensions.gnome.org.

## Riscos

- `NotifyAsync` e `_showNotification` são partes internas do GNOME; podem mudar numa
  versão nova. Mitigação: plano B acima; o pior caso é voltar ao aviso comum.
- St (o toolkit da barra) não tem filtros de CSS: o céu, a pedra e as ameias vêm de
  um SVG de fundo, não de CSS. Se algo do desenho não der para reproduzir, mostro a
  diferença ao usuário antes de seguir.
