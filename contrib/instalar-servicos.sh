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
for unidade in guardiao-monitor.service \
               guardiao-atualizar.service guardiao-atualizar.timer \
               guardiao-varrer-rapida.service guardiao-varrer-rapida.timer \
               guardiao-varrer-completa.service guardiao-varrer-completa.timer; do
    # Os arquivos supõem o projeto em ~/guardiao; aqui vale onde ele estiver.
    sed "s|%h/guardiao|$ORIGEM|g" "$ORIGEM/contrib/$unidade" > "$DESTINO/$unidade"
done

systemctl --user daemon-reload
systemctl --user enable --now guardiao-monitor.service guardiao-atualizar.timer \
    guardiao-varrer-rapida.timer guardiao-varrer-completa.timer
systemctl --user restart guardiao-monitor.service
echo
systemctl --user --no-pager --lines=0 status guardiao-monitor.service | head -3
systemctl --user --no-pager list-timers 'guardiao-*'
