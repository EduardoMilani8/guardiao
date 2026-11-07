#!/bin/sh
cd "$(dirname "$0")"
H='<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#0D1626}</style></head><body>'
{ echo "$H"; cat shared.svg; echo '<div style="display:flex;gap:6px;padding:6px">'; for f in cav-espada3 arq-gravura5 vid car; do echo '<div style="width:128px">'; cat $f.svg; echo '</div>'; done; echo '</div></body></html>'; } > lado.html
{ echo "$H"; cat shared.svg; echo '<div style="width:540px;margin-top:-40px">'; cat car.svg; echo '</div></body></html>'; } > car-cima.html
{ echo "$H"; cat shared.svg; echo '<div style="width:540px;margin-top:-330px">'; cat car.svg; echo '</div></body></html>'; } > car-baixo.html
