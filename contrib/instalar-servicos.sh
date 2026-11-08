#!/bin/sh
# Liga a proteção da sua conta: o monitor (downloads e comportamento), a
# atualização das bases de hora em hora e as varreduras agendadas.
#
#   contrib/instalar-servicos.sh
#
# Sem sudo: são serviços de usuário do systemd. O protetor, que precisa de
# root, tem o instalador próprio (sudo contrib/instalar-protetor.sh).
# Pode rodar de novo quando quiser; ele só substitui os arquivos dos serviços.
set -eu

[ "$(id -u)" != 0 ] || { echo "Rode sem sudo: estes serviços são da sua conta." >&2; exit 1; }
ORIGEM=$(cd "$(dirname "$0")/.." && pwd)
DESTINO=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
[ -x "$ORIGEM/.venv/bin/python" ] || { echo "Crie o ambiente antes: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }

mkdir -p "$DESTINO"

# Quem instalou antes da troca de nome tem os serviços guardiao-*: desliga e apaga,
# para não ficarem dois monitores e duas varreduras agendadas.
ANTIGOS=$(cd "$DESTINO" && ls guardiao-*.service guardiao-*.timer 2>/dev/null || true)
if [ -n "$ANTIGOS" ]; then
    echo "Trocando os serviços antigos do Guardião pelos da Guarnição."
    # shellcheck disable=SC2086
    systemctl --user disable --now $ANTIGOS 2>/dev/null || true
    # shellcheck disable=SC2086
    (cd "$DESTINO" && rm -f $ANTIGOS)
fi

# Até 08/11/2026 a completa começava sozinha todo domingo (e derrubou um jogo
# por falta de memória). Agora ela pergunta antes: o timer antigo sai.
if [ -f "$DESTINO/guarnicao-varrer-completa.timer" ]; then
    systemctl --user disable --now guarnicao-varrer-completa.timer 2>/dev/null || true
    rm -f "$DESTINO/guarnicao-varrer-completa.timer"
fi

for unidade in guarnicao-monitor.service \
               guarnicao-atualizar.service guarnicao-atualizar.timer \
               guarnicao-varrer-rapida.service guarnicao-varrer-rapida.timer \
               guarnicao-varrer-completa.service \
               guarnicao-semanal.service guarnicao-semanal.timer; do
    # Os arquivos supõem o projeto em ~/guarnicao; aqui vale onde ele estiver.
    sed "s|%h/guarnicao|$ORIGEM|g" "$ORIGEM/contrib/$unidade" > "$DESTINO/$unidade"
done

systemctl --user daemon-reload
systemctl --user enable --now guarnicao-monitor.service guarnicao-atualizar.timer \
    guarnicao-varrer-rapida.timer guarnicao-semanal.timer
systemctl --user restart guarnicao-monitor.service
echo
systemctl --user --no-pager --lines=0 status guarnicao-monitor.service | head -3
systemctl --user --no-pager list-timers 'guarnicao-*'
