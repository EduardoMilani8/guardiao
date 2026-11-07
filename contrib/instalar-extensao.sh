#!/usr/bin/env bash
# Instala a extensão do GNOME da Guarnição para o seu usuário (sem sudo):
# o escudo na barra e os avisos com a arte da muralha.
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
uuid="guarnicao@eduardomilani8.github.io"
destino="$HOME/.local/share/gnome-shell/extensions/$uuid"
fontes="$HOME/.local/share/fonts/guarnicao"

if [ ! -x "$raiz/.venv/bin/python" ]; then
  echo "Não achei $raiz/.venv/bin/python. Instale a Guarnição primeiro (veja o README)." >&2
  exit 1
fi

rm -rf "$destino"
mkdir -p "$destino" "$fontes"
cp -r "$raiz/extensao/$uuid/." "$destino/"
# Onde a Guarnição está, para os botões rodarem "python -m guarnicao ...".
"$raiz/.venv/bin/python" -c 'import json, sys; print(json.dumps({"python": sys.argv[1], "pasta": sys.argv[2]}))' \
  "$raiz/.venv/bin/python" "$raiz" > "$destino/config.json"

cp "$raiz"/guarnicao/launcher/estatico/fontes/*.woff2 "$fontes/"
fc-cache -f "$fontes" >/dev/null 2>&1 || true

if gnome-extensions enable "$uuid" 2>/dev/null; then
  echo "Extensão ligada."
else
  # O GNOME que está rodando ainda não conhece a extensão nova: deixa ela marcada
  # como ligada, para carregar sozinha no próximo login.
  "$raiz/.venv/bin/python" - "$uuid" <<'PY'
import ast, subprocess, sys
uuid = sys.argv[1]
atual = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                       capture_output=True, text=True).stdout.strip()
lista = ast.literal_eval(atual.removeprefix("@as ")) if atual else []
if uuid not in lista:
    subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(lista + [uuid])], check=True)
PY
  echo "Extensão marcada para ligar no próximo login."
fi
echo "No Wayland, saia e entre de novo na sessão para o GNOME carregar a extensão."
