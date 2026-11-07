#!/bin/sh
# Instala (ou atualiza) o protetor como serviço do sistema.
#
#   sudo contrib/instalar-protetor.sh
#
# Copia a Guarnição para /opt/guarnicao, de root, com um ambiente Python próprio,
# e liga o serviço guarnicao-protetor. Rode de novo depois de um `git pull`
# para levar o código novo à cópia de root.
set -eu

[ "$(id -u)" = 0 ] || { echo "Rode com sudo." >&2; exit 1; }
USUARIO=${SUDO_USER:?Rode com sudo a partir da sua conta, não como root direto.}
CASA=$(getent passwd "$USUARIO" | cut -d: -f6)
ORIGEM=$(cd "$(dirname "$0")/.." && pwd)
DESTINO=/opt/guarnicao

install -d -o root -g root -m 755 "$DESTINO"
rm -rf "$DESTINO/guarnicao" "$DESTINO/regras" "$DESTINO/assinaturas" "$DESTINO/dados"
cp -r "$ORIGEM/guarnicao" "$ORIGEM/regras" "$ORIGEM/assinaturas" "$ORIGEM/dados" "$DESTINO/"
find "$DESTINO" -name __pycache__ -prune -exec rm -rf {} +
chown -R root:root "$DESTINO"
chmod -R go-w "$DESTINO"

# Mesma versão do yara-x da sua conta: as regras foram calibradas com ela.
YARA=$("$ORIGEM/.venv/bin/python" -m pip freeze 2>/dev/null | grep -i '^yara-x==' || echo yara-x)
[ -x "$DESTINO/.venv/bin/python" ] || python3 -m venv "$DESTINO/.venv"
"$DESTINO/.venv/bin/pip" install -q "$YARA"
chown -R root:root "$DESTINO/.venv"

# Antes da troca de nome o serviço era o guardiao-protetor, com a cópia em
# /opt/guardiao. Desliga o antigo antes de ligar o novo: dois protetores
# responderiam ao kernel pelo mesmo arquivo.
if [ -e /etc/systemd/system/guardiao-protetor.service ]; then
    echo "Trocando o protetor antigo do Guardião pelo da Guarnição."
    systemctl disable --now guardiao-protetor 2>/dev/null || true
    rm -f /etc/systemd/system/guardiao-protetor.service
fi

sed "s|@CASA@|$CASA|g" "$ORIGEM/contrib/guarnicao-protetor.service" > /etc/systemd/system/guarnicao-protetor.service
systemctl daemon-reload
systemctl enable guarnicao-protetor
systemctl restart guarnicao-protetor
sleep 2
systemctl --no-pager --lines=5 status guarnicao-protetor
# A cópia antiga só sai depois que a nova já está de pé.
rm -rf /opt/guardiao
