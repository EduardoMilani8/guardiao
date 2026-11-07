"""Mede a taxa de detecção da Guarnição com amostras recentes do MalwareBazaar.

    .venv/bin/pip install -r ferramentas/requirements.txt
    .venv/bin/python -I ferramentas/medir_deteccao.py --desde 2026-11-05

Baixa as amostras mais recentes de cada tipo (só as vistas a partir de
--desde, para não repetir as de uma medição anterior), analisa cada uma e
apaga tudo no fim. As amostras são só lidas, nunca executadas: ficam numa
pasta 0700, com permissão 0400, e o conteúdo é conferido pelo SHA-256.

A medição é feita *sem* a base de hashes do MalwareBazaar: as amostras vêm
dela, e com ela a taxa seria 100% por construção. O que sobra (ClamAV, YARA
e heurísticas) é o que a Guarnição reconhece de malware que ninguém reportou.

Precisa da chave do MalwareBazaar no ~/.config/guarnicao/config.toml.
"""

import argparse
import collections
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from guarnicao import assinaturas, clamav, regras_yara, scanner  # noqa: E402
from guarnicao.caminhos import ler_config, variavel  # noqa: E402

API = "https://mb-api.abuse.ch/api/v1/"
POR_TIPO = {"elf": 100, "exe": 50, "sh": 25, "js": 25}   # a proporção da medição de 2026-11-04
NOMES = {"elf": "Linux (ELF)", "exe": "Windows (EXE)", "sh": "Shell", "js": "JavaScript"}


def pedir(campos: dict, chave: str) -> bytes:
    req = urllib.request.Request(API, data=urllib.parse.urlencode(campos).encode(),
                                 headers={"Auth-Key": chave, "User-Agent": "guarnicao-medicao"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def baixar(pasta: Path, chave: str, desde: date, por_tipo: dict[str, int]) -> list[dict]:
    import pyzipper   # só a medição precisa dele: a Guarnição em si, não

    amostras = []
    for tipo, quantos in por_tipo.items():
        resposta = json.loads(pedir({"query": "get_file_type", "file_type": tipo, "limit": "1000"}, chave))
        lista = [d for d in resposta.get("data") or []
                 if datetime.fromisoformat(d["first_seen"]).date() >= desde][:quantos]
        print(f"{tipo}: {len(lista)} amostras desde {desde:%d/%m}", flush=True)
        for d in lista:
            sha = d["sha256_hash"]
            try:
                with pyzipper.AESZipFile(io.BytesIO(pedir({"query": "get_file", "sha256_hash": sha}, chave))) as z:
                    z.setpassword(b"infected")
                    [membro] = z.namelist()
                    conteudo = z.read(membro)
            except Exception as erro:   # resposta de erro em JSON, ZIP inesperado, rede
                print(f"  pulada {sha[:12]}: {type(erro).__name__}", flush=True)
                continue
            if hashlib.sha256(conteudo).hexdigest() != sha:
                print(f"  pulada {sha[:12]}: o hash não confere", flush=True)
                continue
            destino = pasta / Path(membro).name
            fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
            with os.fdopen(fd, "wb") as f:
                f.write(conteudo)
            amostras.append({"sha256": sha, "arquivo": destino.name, "tipo": tipo,
                             "familia": d.get("signature") or "", "visto": d["first_seen"]})
            time.sleep(0.3)   # gentileza com o servidor
    return amostras


def medir(pasta: Path, amostras: list[dict]) -> list[dict]:
    banco = assinaturas.Banco(assinaturas.ler_txt(), fontes=[])   # sem o MalwareBazaar
    yara, cl = regras_yara.carregar(), clamav.conectar()
    print(f"ClamAV: {'ligado' if cl else 'DESLIGADO'} · YARA: {'ligado' if yara else 'DESLIGADO'}")
    linhas = []
    for a in amostras:
        arquivo = pasta / a["arquivo"]
        try:
            nome_clamav = cl.verificar(arquivo) if cl else None
        except OSError:
            nome_clamav = None
        ocorrencias = regras_yara.verificar(arquivo, yara) if yara else []
        r = scanner.analisar(arquivo, banco, yara, cl)
        linhas.append({**a, "clamav": nome_clamav,
                       "yara_alta": [o.regra for o in ocorrencias if o.gravidade == "alta"],
                       "veredito": "ameaça" if r.infectado else "suspeito" if r.suspeito else "limpo",
                       "camada": r.camada})
    return linhas


def relatorio(linhas: list[dict]) -> str:
    """Tabela em Markdown, no formato de docs/deteccao.md."""
    tipos = [t for t in POR_TIPO if any(l["tipo"] == t for l in linhas)]
    grupos = [("Todas", linhas)] + [(NOMES[t], [l for l in linhas if l["tipo"] == t]) for t in tipos]

    def taxa(filtro, grupo):
        return f"{100 * sum(1 for l in grupo if filtro(l)) / len(grupo):.1f}%".replace(".", ",") if grupo else "-"

    medidas = [
        ("ClamAV sozinho", lambda l: l["clamav"]),
        ("Regras YARA sozinhas", lambda l: l["yara_alta"]),
        ("**Guarnição: ameaça**", lambda l: l["veredito"] == "ameaça"),
        ("**Guarnição: ameaça ou suspeito**", lambda l: l["veredito"] != "limpo"),
    ]
    saida = ["| | " + " | ".join(f"{n} ({len(g)})" for n, g in grupos) + " |",
             "|---" * (len(grupos) + 1) + "|"]
    saida += [f"| {nome} | " + " | ".join(taxa(f, g) for _, g in grupos) + " |" for nome, f in medidas]
    escaparam = collections.Counter(f"{l['tipo']}/{l['familia'] or '?'}" for l in linhas if l["veredito"] == "limpo")
    saida.append("\nO que mais escapou: " + ", ".join(f"{k} ({n})" for k, n in escaparam.most_common(8)))
    return "\n".join(saida)


def main() -> int:
    p = argparse.ArgumentParser(description="Mede a taxa de detecção com amostras do MalwareBazaar.")
    p.add_argument("--desde", type=date.fromisoformat, required=True,
                   help="só amostras vistas a partir deste dia (AAAA-MM-DD); use o dia seguinte à última medição")
    p.add_argument("--limite", type=int, help="no máximo N amostras por tipo (padrão: 100 ELF, 50 EXE, 25 shell, 25 JS)")
    p.add_argument("--saida", type=Path, help="grava o resultado de cada amostra (só metadados) neste JSON")
    args = p.parse_args()

    chave = variavel("MALWAREBAZAAR_CHAVE") or ler_config().get("malwarebazaar", {}).get("chave")
    if not chave:
        print("Sem a chave do MalwareBazaar no ~/.config/guarnicao/config.toml.", file=sys.stderr)
        return 1
    por_tipo = {t: args.limite or n for t, n in POR_TIPO.items()}

    pasta = Path(tempfile.mkdtemp(prefix="guarnicao-medicao-"))   # 0700
    try:
        amostras = baixar(pasta, chave, args.desde, por_tipo)
        if not amostras:
            print("Nenhuma amostra nesse período.")
            return 1
        linhas = medir(pasta, amostras)
    finally:
        shutil.rmtree(pasta)   # as amostras nunca ficam no disco
        print(f"Amostras apagadas ({pasta}).")

    if args.saida:
        args.saida.write_text(json.dumps(linhas, indent=1, ensure_ascii=False))
    print(f"\nMedido em {date.today():%d/%m/%Y} com {len(linhas)} amostras vistas desde {args.desde:%d/%m/%Y}:\n")
    print(relatorio(linhas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
