"""Linha de comando.

    python -m guardiao varrer ~/Downloads [--isolar]
    python -m guardiao varrer --rapida | --completa [--isolar] [--sem-cache]
    python -m guardiao atualizar [--forcar | --status]
    python -m guardiao monitorar [pastas...] [--isolar]
    python -m guardiao dev [pasta] [--todos]
    python -m guardiao cacar [--todos] [--sem-pacotes]
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


def avisar_camadas_desligadas() -> None:
    from . import clamav
    if not regras_yara.disponivel():
        print(f"{CINZA}yara-x não instalado: camada de regras desativada (pip install yara-x){FIM}")
    if clamav.conectar() is None:
        print(f"{CINZA}ClamAV não encontrado: camada desativada (sudo apt install clamav clamav-daemon){FIM}")


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
    from . import varredura

    if args.completa:
        raizes, nome, repetir = varredura.raizes_completa(args.incluir_externos), "completa", "--completa"
    elif args.rapida:
        raizes, nome, repetir = varredura.raizes_rapida(), "rápida", "--rapida"
    elif args.alvo:
        alvo = Path(args.alvo).expanduser()
        if not alvo.exists():
            print(f"{VERMELHO}Não encontrado: {alvo}{FIM}")
            return 2
        raizes, nome, repetir = [alvo.resolve()], str(alvo), str(alvo.resolve())
    else:
        print("Diga o que varrer: um caminho, --rapida ou --completa.")
        return 2

    avisar_camadas_desligadas()
    from . import bases
    for aviso in bases.avisos():
        print(f"{AMARELO}Base desatualizada: {aviso}{FIM}")
    processos = args.processos or os.cpu_count() or 1
    print(f"Varredura {nome}: {len(raizes)} ponto(s) de partida, até {processos} processos")
    terminal = sys.stdout.isatty()
    resumo = varredura.Resumo()

    for item in varredura.executar(raizes, usar_cache=not args.sem_cache, processos=processos):
        if isinstance(item, varredura.Progresso):
            if terminal:
                contagem = f"{item.vistos}/{item.total}" if item.total else f"{item.vistos}"
                fase = "Listando" if item.fase == "listando" else "Analisando"
                print(f"\r\033[K{CINZA}{fase} {contagem}  {item.atual[-70:]}{FIM}", end="", flush=True)
        elif isinstance(item, varredura.Resumo):
            resumo = item
        elif isinstance(item, scanner.Resultado) and (item.infectado or item.suspeito):
            if terminal:
                print("\r\033[K", end="")
            relatar(item, args.isolar)
    if terminal:
        print("\r\033[K", end="")

    total = resumo.analisados + resumo.em_cache
    cor = VERDE if resumo.ameacas == resumo.suspeitos == 0 else VERMELHO
    print(f"\n{cor}{total} arquivos verificados · {resumo.ameacas} ameaças · {resumo.suspeitos} suspeitos"
          f" · {resumo.segundos:.1f}s{FIM}")
    print(f"{CINZA}{resumo.analisados} analisados agora, {resumo.em_cache} sem mudanças desde a última vez{FIM}")
    if resumo.grandes:
        print(f"{CINZA}{resumo.grandes} arquivos acima do limite de tamanho foram pulados{FIM}")
    if resumo.sem_permissao and os.geteuid() != 0:
        print(f"{CINZA}{resumo.sem_permissao} itens sem permissão de leitura. Para incluir os arquivos do sistema:\n"
              f"  sudo .venv/bin/python -m guardiao varrer {repetir}{FIM}")
    return 1 if resumo.ameacas else 0


def _ha_quanto(segundos: float | None) -> str:
    if segundos is None:
        return "nunca"
    for tamanho, unidade in ((86400, "dia(s)"), (3600, "h"), (60, "min")):
        if segundos >= tamanho:
            return f"há {int(segundos // tamanho)} {unidade}"
    return f"há {int(segundos)} s"


def _status_clamav() -> None:
    from . import clamav
    cliente = clamav.conectar()
    if cliente is None:
        print(f"{CINZA}{'clamav':<14} {'desligado':<14} instale: sudo apt install clamav clamav-daemon{FIM}")
        return
    motor, numero, quando = cliente.versao()
    idade = None if quando is None else time.time() - quando.timestamp()
    from . import bases
    cor = VERMELHO if idade is None or idade > bases.VELHA_APOS else CINZA
    print(f"{cor}{'clamav':<14} {'freshclam':<14} versão {numero or '-'} · assinaturas {_ha_quanto(idade)} ({motor}){FIM}")


def cmd_atualizar(args) -> int:
    from . import bases

    lista = bases.registradas()
    if not lista:
        print("Nenhuma base externa configurada ainda.")
        return 0
    if args.status:
        relatorios = [bases.Relatorio(b.nome, "status", bases.ler_estado(b)) for b in lista]
    else:
        try:
            relatorios = bases.atualizar(lista, forcar=args.forcar)
        except bases.Ocupado as erro:
            print(f"{AMARELO}{erro}{FIM}")
            return 1
    falhou = False
    _status_clamav()
    from .fontes.malwarebazaar import MalwareBazaar
    if not MalwareBazaar.chave():
        print(f"{CINZA}{'malwarebazaar':<14} {'desligado':<14} sem chave: crie uma grátis em "
              f"https://auth.abuse.ch e ponha em ~/.config/guardiao/config.toml{FIM}")
    for r in relatorios:
        e = r.estado
        velha = e.idade() is None or e.idade() > bases.VELHA_APOS
        cor = VERMELHO if r.situacao == "erro" or velha else VERDE if r.situacao == "atualizada" else CINZA
        print(f"{cor}{r.base:<14} {r.situacao:<14} versão {e.versao or '-'} · conferida {_ha_quanto(e.idade())}{FIM}")
        if e.erro:
            falhou = True
            print(f"               {e.erro}")
            if e.versao:
                print("               segue valendo a versão anterior")
    return 1 if falhou else 0


def cmd_monitorar(args) -> int:
    from . import monitor   # watchdog só é necessário para este comando

    pastas = [Path(p).expanduser() for p in (args.pastas or ["~/Downloads"])]
    for pasta in pastas:
        if not pasta.is_dir():
            print(f"{VERMELHO}Pasta não encontrada: {pasta}{FIM}")
            return 2
    avisar_camadas_desligadas()
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
    avisar_camadas_desligadas()

    achados = dev.auditar(raiz)
    return imprimir_achados(achados, args.todos, raiz)


def imprimir_achados(achados, todos: bool, raiz: Path | None = None) -> int:
    """Achados do `dev` e do `cacar`. Retorna 1 se houver algum de alto risco."""
    estilo = {"alta": (VERMELHO, "[ALTO]   "), "media": (AMARELO, "[atenção]"), "info": (CINZA, "[info]   ")}
    contagem = {"alta": 0, "media": 0, "info": 0}
    for a in achados:
        contagem[a.gravidade] = contagem.get(a.gravidade, 0) + 1
        if a.gravidade == "info" and not todos:
            continue
        cor, rotulo = estilo.get(a.gravidade, (FIM, "[?]      "))
        local = a.arquivo.relative_to(raiz) if raiz and a.arquivo.is_relative_to(raiz) else a.arquivo
        print(f"{cor}{rotulo} {a.categoria} · {local}{FIM}")
        print(f"           {a.mensagem}")

    cor = VERMELHO if contagem["alta"] else AMARELO if contagem["media"] else VERDE
    escondidos = "" if todos or not contagem["info"] else " (--todos para ver)"
    print(f"\n{cor}{contagem['alta']} alto risco · {contagem['media']} atenção · "
          f"{contagem['info']} informativos{escondidos}{FIM}")
    return 1 if contagem["alta"] else 0


def cmd_cacar(args) -> int:
    from . import cacador

    avisar_camadas_desligadas()
    from . import clamav
    julgar = cacador.Juiz(assinaturas.carregar(), regras_yara.carregar(), clamav.conectar())
    if os.geteuid() != 0:
        print(f"{CINZA}Sem root, só os seus processos são verificados. Para todos:\n"
              f"  sudo .venv/bin/python -m guardiao cacar{FIM}")
    print("Procurando bibliotecas injetadas, processos estranhos e persistência...")
    if not args.sem_pacotes:
        print(f"{CINZA}Conferindo os arquivos dos pacotes com o dpkg (uns 30 s; --sem-pacotes pula){FIM}")
    return imprimir_achados(cacador.cacar(julgar, conferir_pacotes=not args.sem_pacotes), args.todos)


def cmd_launcher(args) -> int:
    import webbrowser

    from .launcher import servidor

    if os.geteuid() == 0:
        # Um servidor web como root daria a qualquer falha nele o poder do root.
        print(f"{VERMELHO}Não rode o launcher como root. Para varrer o sistema todo: "
              f"sudo .venv/bin/python -m guardiao varrer --completa{FIM}")
        return 2
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

    p_varrer = sub.add_parser("varrer", help="analisa um arquivo, uma pasta ou o computador")
    p_varrer.add_argument("alvo", nargs="?")
    modo = p_varrer.add_mutually_exclusive_group()
    modo.add_argument("--rapida", action="store_true", help="onde malware costuma chegar ou se instalar")
    modo.add_argument("--completa", action="store_true", help="o disco inteiro")
    p_varrer.add_argument("--isolar", action="store_true", help="move ameaças para a quarentena")
    p_varrer.add_argument("--sem-cache", action="store_true", help="reanalisa mesmo o que não mudou")
    p_varrer.add_argument("--processos", type=int, help="padrão: um por núcleo")
    p_varrer.add_argument("--incluir-externos", action="store_true", help="inclui /media e /mnt na completa")
    p_varrer.set_defaults(func=cmd_varrer)

    p_at = sub.add_parser("atualizar", help="baixa as bases de detecção mais recentes")
    modo_at = p_at.add_mutually_exclusive_group()
    modo_at.add_argument("--forcar", action="store_true", help="baixa de novo mesmo se estiver em dia")
    modo_at.add_argument("--status", action="store_true", help="só mostra a situação de cada base")
    p_at.set_defaults(func=cmd_atualizar)

    p_mon = sub.add_parser("monitorar", help="analisa em tempo real os arquivos que chegam")
    p_mon.add_argument("pastas", nargs="*", help="padrão: ~/Downloads")
    p_mon.add_argument("--isolar", action="store_true", help="move ameaças para a quarentena")
    p_mon.set_defaults(func=cmd_monitorar)

    p_dev = sub.add_parser("dev", help="audita um projeto: pacotes, scripts de instalação, auto-execução")
    p_dev.add_argument("pasta", nargs="?", default=".", help="padrão: pasta atual")
    p_dev.add_argument("--todos", action="store_true", help="mostra também os achados informativos")
    p_dev.set_defaults(func=cmd_dev)

    p_c = sub.add_parser("cacar", help="caça persistência e rootkits já instalados no sistema")
    p_c.add_argument("--todos", action="store_true", help="mostra também os achados informativos")
    p_c.add_argument("--sem-pacotes", action="store_true", help="pula o dpkg --verify (o passo mais lento)")
    p_c.set_defaults(func=cmd_cacar)

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
