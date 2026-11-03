"""Linha de comando.

    python -m guardiao varrer ~/Downloads [--isolar]
    python -m guardiao quarentena listar
    python -m guardiao quarentena restaurar <id>
"""

import argparse
import sys
from pathlib import Path

from . import assinaturas, quarentena, scanner

VERMELHO, AMARELO, VERDE, CINZA, FIM = "\033[31m", "\033[33m", "\033[32m", "\033[90m", "\033[0m"


def cmd_varrer(args) -> int:
    banco = assinaturas.carregar()
    total = ameacas = suspeitos = 0

    for item in scanner.varrer(Path(args.alvo).expanduser(), banco):
        if isinstance(item, tuple):
            caminho, erro = item
            print(f"{CINZA}[pulado]   {caminho}: {erro.strerror}{FIM}")
            continue

        total += 1
        if item.infectado:
            ameacas += 1
            print(f"{VERMELHO}[AMEAÇA]   {item.caminho}  →  {item.ameaca}{FIM}")
            if args.isolar:
                id_ = quarentena.isolar(item.caminho, item.sha256, item.ameaca)
                print(f"           isolado na quarentena (id {id_})")
        elif item.suspeito:
            suspeitos += 1
            print(f"{AMARELO}[suspeito] {item.caminho}  ({item.pontuacao}/100){FIM}")
            for motivo in item.motivos:
                print(f"           - {motivo}")

    cor = VERDE if ameacas == suspeitos == 0 else VERMELHO
    print(f"\n{cor}{total} arquivos analisados · {ameacas} ameaças · {suspeitos} suspeitos{FIM}")
    return 1 if ameacas else 0


def cmd_quarentena(args) -> int:
    if args.acao == "listar":
        entradas = quarentena.listar()
        if not entradas:
            print("Quarentena vazia.")
        for e in entradas:
            print(f"{e['id']}  {e['data']}  {e['motivo']}\n              {e['original']}")
    else:
        destino = quarentena.restaurar(args.id)
        print(f"Restaurado em {destino} (sem permissão de execução).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="guardiao", description="Antivírus de estudo")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_varrer = sub.add_parser("varrer", help="analisa um arquivo ou pasta")
    p_varrer.add_argument("alvo")
    p_varrer.add_argument("--isolar", action="store_true", help="move ameaças para a quarentena")
    p_varrer.set_defaults(func=cmd_varrer)

    p_q = sub.add_parser("quarentena", help="gerencia arquivos isolados")
    q_sub = p_q.add_subparsers(dest="acao", required=True)
    q_sub.add_parser("listar")
    q_sub.add_parser("restaurar").add_argument("id")
    p_q.set_defaults(func=cmd_quarentena)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
