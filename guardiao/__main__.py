"""Linha de comando.

    python -m guardiao varrer ~/Downloads [--isolar]
    python -m guardiao monitorar [pastas...] [--isolar]
    python -m guardiao dev [pasta] [--todos]
    python -m guardiao launcher [--porta 8765] [--sem-navegador]
    python -m guardiao quarentena listar
    python -m guardiao quarentena restaurar <id>
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from . import assinaturas, notificacao, quarentena, regras_yara, scanner

VERMELHO, AMARELO, VERDE, CINZA, FIM = "\033[31m", "\033[33m", "\033[32m", "\033[90m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):   # ex.: journal do systemd
    VERMELHO = AMARELO = VERDE = CINZA = FIM = ""


def avisar_se_sem_yara() -> None:
    if not regras_yara.disponivel():
        print(f"{CINZA}yara-x não instalado: camada de regras desativada (pip install yara-x){FIM}")


def relatar(item: scanner.Resultado, isolar: bool) -> str | None:
    """Imprime ameaças e suspeitos. Retorna o id da quarentena, se isolou."""
    if item.infectado:
        print(f"{VERMELHO}[AMEAÇA]   {item.caminho}  →  {item.ameaca}{FIM}")
        if isolar:
            id_ = quarentena.isolar(item.caminho, item.sha256, item.ameaca)
            print(f"           isolado na quarentena (id {id_})")
            return id_
    elif item.suspeito:
        print(f"{AMARELO}[suspeito] {item.caminho}  ({item.pontuacao}/100){FIM}")
        for motivo in item.motivos:
            print(f"           - {motivo}")
    return None


def cmd_varrer(args) -> int:
    avisar_se_sem_yara()
    banco, yara = assinaturas.carregar(), regras_yara.carregar()
    total = ameacas = suspeitos = 0

    for item in scanner.varrer(Path(args.alvo).expanduser(), banco, yara):
        if isinstance(item, tuple):
            caminho, erro = item
            print(f"{CINZA}[pulado]   {caminho}: {erro.strerror or erro}{FIM}")
            continue
        total += 1
        ameacas += item.infectado
        suspeitos += item.suspeito
        relatar(item, args.isolar)

    cor = VERDE if ameacas == suspeitos == 0 else VERMELHO
    print(f"\n{cor}{total} arquivos analisados · {ameacas} ameaças · {suspeitos} suspeitos{FIM}")
    return 1 if ameacas else 0


def cmd_monitorar(args) -> int:
    from . import monitor   # watchdog só é necessário para este comando

    pastas = [Path(p).expanduser() for p in (args.pastas or ["~/Downloads"])]
    for pasta in pastas:
        if not pasta.is_dir():
            print(f"{VERMELHO}Pasta não encontrada: {pasta}{FIM}")
            return 2
    avisar_se_sem_yara()
    banco = assinaturas.carregar()

    def ao_analisar(item: scanner.Resultado) -> None:
        id_ = relatar(item, args.isolar)
        if item.infectado:
            acao = "Movido para a quarentena." if id_ else "Não foi isolado (rode com --isolar)."
            notificacao.notificar("Ameaça detectada", f"{item.caminho.name}: {item.ameaca}\n{acao}", urgente=True)
        elif item.suspeito:
            notificacao.notificar(
                f"Arquivo suspeito ({item.pontuacao}/100)",
                f"{item.caminho.name}\n{item.motivos[0] if item.motivos else ''}",
            )
        else:
            print(f"{CINZA}[limpo]    {item.caminho}{FIM}")

    def ao_erro(caminho: Path, erro: Exception) -> None:
        print(f"{CINZA}[pulado]   {caminho}: {getattr(erro, 'strerror', None) or erro}{FIM}")

    def ao_sigterm(*_):
        raise KeyboardInterrupt   # `systemctl stop` encerra igual a um Ctrl+C

    signal.signal(signal.SIGTERM, ao_sigterm)
    print(f"{VERDE}Vigiando {', '.join(map(str, pastas))}  (Ctrl+C para sair){FIM}")
    with monitor.Monitor(pastas, banco, ao_analisar, ao_erro):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitor encerrado.")
    return 0


def cmd_dev(args) -> int:
    from . import dev

    raiz = Path(args.pasta).expanduser().resolve()
    if not raiz.is_dir():
        print(f"{VERMELHO}Pasta não encontrada: {raiz}{FIM}")
        return 2
    avisar_se_sem_yara()

    achados = dev.auditar(raiz)
    estilo = {"alta": (VERMELHO, "[ALTO]   "), "media": (AMARELO, "[atenção]"), "info": (CINZA, "[info]   ")}
    contagem = {"alta": 0, "media": 0, "info": 0}
    for a in achados:
        contagem[a.gravidade] = contagem.get(a.gravidade, 0) + 1
        if a.gravidade == "info" and not args.todos:
            continue
        cor, rotulo = estilo.get(a.gravidade, (FIM, "[?]      "))
        local = a.arquivo.relative_to(raiz) if a.arquivo.is_relative_to(raiz) else a.arquivo
        print(f"{cor}{rotulo} {a.categoria} · {local}{FIM}")
        print(f"           {a.mensagem}")

    cor = VERMELHO if contagem["alta"] else AMARELO if contagem["media"] else VERDE
    escondidos = "" if args.todos or not contagem["info"] else " (--todos para ver)"
    print(f"\n{cor}{contagem['alta']} alto risco · {contagem['media']} atenção · "
          f"{contagem['info']} informativos{escondidos}{FIM}")
    return 1 if contagem["alta"] else 0


def cmd_launcher(args) -> int:
    import webbrowser

    from .launcher import servidor

    try:
        srv = servidor.criar_servidor(args.porta)
    except OSError as erro:
        print(f"{VERMELHO}Não consegui abrir a porta {args.porta}: {erro.strerror}{FIM}")
        return 2
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"{VERDE}Launcher (protótipo) em {url}  (Ctrl+C para sair){FIM}")
    if not args.sem_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nLauncher encerrado.")
    finally:
        srv.server_close()
    return 0


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

    p_mon = sub.add_parser("monitorar", help="analisa em tempo real os arquivos que chegam")
    p_mon.add_argument("pastas", nargs="*", help="padrão: ~/Downloads")
    p_mon.add_argument("--isolar", action="store_true", help="move ameaças para a quarentena")
    p_mon.set_defaults(func=cmd_monitorar)

    p_dev = sub.add_parser("dev", help="audita um projeto: pacotes, scripts de instalação, auto-execução")
    p_dev.add_argument("pasta", nargs="?", default=".", help="padrão: pasta atual")
    p_dev.add_argument("--todos", action="store_true", help="mostra também os achados informativos")
    p_dev.set_defaults(func=cmd_dev)

    p_l = sub.add_parser("launcher", help="abre o protótipo do launcher com os guardiões")
    p_l.add_argument("--porta", type=int, default=8765)
    p_l.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    p_l.set_defaults(func=cmd_launcher)

    p_q = sub.add_parser("quarentena", help="gerencia arquivos isolados")
    q_sub = p_q.add_subparsers(dest="acao", required=True)
    q_sub.add_parser("listar")
    q_sub.add_parser("restaurar").add_argument("id")
    p_q.set_defaults(func=cmd_quarentena)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
