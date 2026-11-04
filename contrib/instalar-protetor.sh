#!/bin/sh
# Instala (ou atualiza) o protetor como serviço do sistema.
#
#   sudo contrib/instalar-protetor.sh
#
# Copia o Guardião para /opt/guardiao, de root, com um ambiente Python próprio,
# e liga o serviço guardiao-protetor. Rode de novo depois de um `git pull`
# para levar o código novo à cópia de root.
set -eu

[ "$(id -u)" = 0 ] || { echo "Rode com sudo." >&2; exit 1; }
USUARIO=${SUDO_USER:?Rode com sudo a partir da sua conta, não como root direto.}
CASA=$(getent passwd "$USUARIO" | cut -d: -f6)
ORIGEM=$(cd "$(dirname "$0")/.." && pwd)
DESTINO=/opt/guardiao

install -d -o root -g root -m 755 "$DESTINO"
rm -rf "$DESTINO/guardiao" "$DESTINO/regras" "$DESTINO/assinaturas" "$DESTINO/dados"
cp -r "$ORIGEM/guardiao" "$ORIGEM/regras" "$ORIGEM/assinaturas" "$ORIGEM/dados" "$DESTINO/"
find "$DESTINO" -name __pycache__ -prune -exec rm -rf {} +
chown -R root:root "$DESTINO"
chmod -R go-w "$DESTINO"

# Mesma versão do yara-x da sua conta: as regras foram calibradas com ela.
YARA=$("$ORIGEM/.venv/bin/pip" freeze 2>/dev/null | grep -i '^yara-x==' || echo yara-x)
[ -x "$DESTINO/.venv/bin/python" ] || python3 -m venv "$DESTINO/.venv"
"$DESTINO/.venv/bin/pip" install -q "$YARA"
chown -R root:root "$DESTINO/.venv"

sed "s|@CASA@|$CASA|g" "$ORIGEM/contrib/guardiao-protetor.service" > /etc/systemd/system/guardiao-protetor.service
systemctl daemon-reload
systemctl enable guardiao-protetor
systemctl restart guardiao-protetor
sleep 2
systemctl --no-pager --lines=5 status guardiao-protetor
