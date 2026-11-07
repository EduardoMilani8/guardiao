"""Importado pelo forkserver (regras_yara.contexto): compila as regras uma vez,
e todo processo que nasce dele já as tem, divididas na memória."""

from . import regras_yara

try:
    regras_yara.preparar_compartilhadas()
except Exception:   # noqa: BLE001 — nunca derrubar o forkserver: os filhos compilam sozinhos
    pass
