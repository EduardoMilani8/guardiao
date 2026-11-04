"""Linha de comando.

    python -m guardiao varrer ~/Downloads [--isolar]
    python -m guardiao varrer --rapida | --completa [--isolar] [--sem-cache] [--agendada]
    python -m guardiao historico [--achados]
    python -m guardiao atualizar [--forcar | --status]
    python -m guardiao monitorar [pastas...] [--isolar] [--sem-comportamento]
    python -m guardiao dev [pasta] [--todos]
    python -m guardiao cacar [--todos] [--sem-pacotes]
    sudo python -m guardiao proteger [--so-avisar] [--prazo 2]
    python -m guardiao launcher [--porta 8765] [--sem-navegador]
    python -m guardiao virustotal <arquivo>
    python -m guardiao quarentena listar
    python -m guardiao quarentena restaurar <id>
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from . import assinaturas, notificacao, quarentena, regras_yara, scanner, virustotal

MAX_VIRUSTOTAL_POR_VARREDURA = 20   # com o cache, a próxima varredura continua de onde esta parou
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


class ConsultaVirusTotal:
    """Junta o laudo do VirusTotal a um resultado, se houver chave. Respeita o
    limite por minuto esperando a vaga; quando acaba a cota do dia (ou a desta
    varredura), avisa uma vez e para de consultar."""

    def __init__(self, maximo: int | None = None):
        self.chave = virustotal.chave()
        self.maximo, self.feitas, self.parou = maximo, 0, False

    def __call__(self, item: scanner.Resultado) -> scanner.Resultado:
        if not self.chave or self.parou or item.infectado:
            return item
        if self.maximo is not None and self.feitas >= self.maximo:
            self._parar(f"{self.maximo} consultas nesta varredura; o resto fica para a próxima")
            return item
        while True:
            try:
                laudo = virustotal.consultar(item.sha256, self.chave)
                self.feitas += 1
                return virustotal.aplicar(item, laudo)
            except virustotal.SemCota as erro:
                if erro.espera is None:
                    self._parar(str(erro))
                    return item
                time.sleep(erro.espera)
            except OSError as erro:
                print(f"{CINZA}VirusTotal não respondeu sobre {item.caminho.name}: {erro}{FIM}")
                return item

    def _parar(self, motivo: str) -> None:
        self.parou = True
        print(f"{CINZA}VirusTotal: {motivo}.{FIM}")


def cmd_virustotal(args) -> int:
    arquivo = Path(args.arquivo).expanduser()
    if not arquivo.is_file():
        print(f"{VERMELHO}Não encontrado: {arquivo}{FIM}")
        return 2
    chave = virustotal.chave()
    if not chave:
        print("Sem chave do VirusTotal. Crie uma grátis em https://www.virustotal.com e coloque no")
        print("~/.config/guardiao/config.toml:\n\n[virustotal]\nchave = \"...\"")
        return 2
    sha = scanner.calcular_sha256(arquivo)
    print(f"{CINZA}Consultando o SHA-256 {sha} (o arquivo não é enviado){FIM}")
    try:
        laudo = virustotal.consultar(sha, chave)
    except (virustotal.SemCota, OSError) as erro:
        print(f"{VERMELHO}Não deu para consultar: {erro}{FIM}")
        return 2
    if not laudo.conhecido:
        print("O VirusTotal nunca viu este arquivo.")
        return 0
    cor = VERMELHO if laudo.maliciosos >= virustotal.MINIMO_AMEACA else \
        AMARELO if laudo.maliciosos else VERDE
    print(f"{cor}{laudo.maliciosos} de {laudo.total} antivírus apontam como malicioso"
          f"{f'  ({laudo.nome})' if laudo.nome else ''}{FIM}")
    print(f"{CINZA}https://www.virustotal.com/gui/file/{sha}{FIM}")
    return 1 if laudo.maliciosos >= virustotal.MINIMO_AMEACA else 0


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
    from datetime import datetime

    from . import bases, historico
    for aviso in bases.avisos():
        print(f"{AMARELO}Base desatualizada: {aviso}{FIM}")
    processos = args.processos or os.cpu_count() or 1
    print(f"Varredura {nome}: {len(raizes)} ponto(s) de partida, até {processos} processos")
    terminal = sys.stdout.isatty()
    resumo = varredura.Resumo()
    inicio, achados = datetime.now(), []
    # Só os suspeitos: o VirusTotal desempata o que o Guardião não teve certeza.
    consultar_vt, promovidos = ConsultaVirusTotal(maximo=MAX_VIRUSTOTAL_POR_VARREDURA), 0

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
            if item.suspeito and consultar_vt(item).infectado:
                promovidos += 1
            achados.append(historico.achado(item, relatar(item, args.isolar)))
    if terminal:
        print("\r\033[K", end="")
    resumo.ameacas, resumo.suspeitos = resumo.ameacas + promovidos, resumo.suspeitos - promovidos
    historico.registrar(historico.novo(nome, "agendada" if args.agendada else "terminal", inicio, resumo, achados))

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
    if args.agendada:
        # Agendada: ninguém está olhando o terminal. Avisa, e quem decide trancar é
        # você, no launcher: um alarme falso no disco inteiro não some sem você ver.
        if resumo.ameacas or resumo.suspeitos:
            notificacao.notificar(
                f"Varredura {nome}: {resumo.ameacas} ameaça(s), {resumo.suspeitos} suspeito(s)",
                "Abra o launcher para ver e trancar: python -m guardiao launcher",
                urgente=bool(resumo.ameacas))
        return 0   # "falhou" no systemd fica para quando a varredura quebrar
    return 1 if resumo.ameacas else 0


def cmd_historico(args) -> int:
    from . import historico

    registros = historico.listar(args.quantos)
    if not registros:
        print("Nenhuma varredura registrada ainda.")
        return 0
    for tipo in ("rápida", "completa"):
        ultima = historico.ultima(tipo)
        quando = ultima.quando.strftime("%d/%m %H:%M") if ultima else "nunca"
        print(f"Última varredura {tipo}: {quando}")
    print()
    print(f"{'quando':<12} {'tipo':<22} {'origem':<9} {'arquivos':>9} {'tempo':>7}  resultado")
    for r in registros:
        # Decide pelo número, não pela cor: fora de um terminal as cores são "".
        achou = r.ameacas or r.suspeitos
        cor = VERMELHO if r.ameacas else AMARELO if r.suspeitos else ""
        resultado = f"{r.ameacas} ameaça(s), {r.suspeitos} suspeito(s)" if achou else "limpo"
        tipo = r.tipo if len(r.tipo) <= 22 else "…" + r.tipo[-21:]
        print(f"{cor}{r.quando.strftime('%d/%m %H:%M'):<12} {tipo:<22} {r.origem:<9} {r.total:>9} "
              f"{r.segundos:>6.0f}s  {resultado}{FIM if achou else ''}")
        if args.achados:
            for a in r.achados:
                cela = f"  (na quarentena: {a['quarentena']})" if a.get("quarentena") else ""
                print(f"{CINZA}             {a['veredito']:<9} {a['caminho']}  {a['ameaca'] or ''}{cela}{FIM}")
    return 0


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
    parado = bases.freshclam_parado()
    cor = VERMELHO if parado or idade is None or idade > bases.VELHA_APOS else CINZA
    estado = "parado" if parado else "freshclam"
    print(f"{cor}{'clamav':<14} {estado:<14} versão {numero or '-'} · assinaturas {_ha_quanto(idade)} ({motor}){FIM}")
    if parado:
        print(f"{VERMELHO}{'':<29}o freshclam não está rodando; para ligar: {bases.LIGAR_FRESHCLAM}{FIM}")


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
    consultar_vt = ConsultaVirusTotal()
    if consultar_vt.chave:
        print(f"{VERDE}Downloads novos também são conferidos no VirusTotal (só o hash){FIM}")

    def ao_analisar(item: scanner.Resultado) -> None:
        item = consultar_vt(item)
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

    def ao_alertar(alerta) -> None:
        cor = VERMELHO if alerta.gravidade == "alta" else AMARELO
        print(f"{cor}[{alerta.tipo.upper()}] {alerta.processo.exe}  →  {alerta.mensagem}{FIM}")
        notificacao.notificar(f"Comportamento perigoso: {alerta.tipo}", alerta.mensagem,
                              urgente=alerta.gravidade == "alta")

    signal.signal(signal.SIGTERM, ao_sigterm)
    print(f"{VERDE}Vigiando {', '.join(map(str, pastas))}  (Ctrl+C para sair){FIM}")
    from contextlib import nullcontext

    from . import comportamento
    vigia = nullcontext() if args.sem_comportamento else comportamento.Vigia(ao_alertar)
    if not args.sem_comportamento:
        print(f"{VERDE}Vigiando também o comportamento dos processos (shells reversos, mineradores){FIM}")
    with monitor.Monitor(pastas, banco, ao_analisar, ao_erro), vigia:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitor encerrado.")
    return 0


def cmd_proteger(args) -> int:
    from . import protetor

    if os.geteuid() != 0:
        print(f"{VERMELHO}O protetor precisa de root: o kernel só dá o fanotify de permissão a ele.{FIM}")
        print("Instalação como serviço: veja contrib/guardiao-protetor.service")
        return 2
    codigo = Path(protetor.__file__).parent
    if any(os.stat(p).st_uid != 0 or os.stat(p).st_mode & 0o022 for p in (codigo, *codigo.glob("*.py"))):
        # Um serviço root rodando código que sua conta pode alterar é um atalho
        # para root: qualquer malware na sua conta trocaria o Guardião.
        print(f"{AMARELO}Atenção: {codigo} pode ser alterado por um usuário comum. "
              f"Para o serviço, use a cópia de root em /opt/guardiao.{FIM}")
    avisar_camadas_desligadas()

    def ao_decidir(d: protetor.Decisao) -> None:
        nome = d.resultado.ameaca if d.resultado and d.resultado.ameaca else ""
        if d.motivo == "ameaça" and not d.permitido:
            print(f"{VERMELHO}[BLOQUEADO] {d.caminho}  →  {nome}  (pedido por {d.quem}, pid {d.pid}){FIM}")
            notificacao.notificar("Guardião bloqueou uma ameaça", f"{d.caminho}\n{nome}", urgente=True)
        elif d.motivo == "ameaça":
            print(f"{VERMELHO}[AMEAÇA]    {d.caminho}  →  {nome}  (só avisando; pid {d.pid}){FIM}")
            notificacao.notificar("Ameaça executada (modo só avisar)", f"{d.caminho}\n{nome}", urgente=True)
        elif d.motivo == "prazo":
            print(f"{VERMELHO}[RODOU]     {d.caminho}  →  {nome}  (a análise passou do prazo; pid {d.pid}){FIM}")
            notificacao.notificar("Ameaça rodou antes do veredito",
                                  f"{d.caminho}\n{nome}\nPara encerrar: sudo kill {d.pid}", urgente=True)
        elif d.motivo == "suspeito" and d.resultado:
            print(f"{AMARELO}[suspeito]  {d.caminho}  ({d.resultado.pontuacao}/100, executado){FIM}")
            notificacao.notificar(f"Executado um arquivo suspeito ({d.resultado.pontuacao}/100)",
                                  f"{d.caminho}\n{d.resultado.motivos[0] if d.resultado.motivos else ''}")
        else:
            print(f"{CINZA}[erro]      {d.caminho}: liberado sem análise{FIM}")

    def ao_sigterm(*_):
        raise KeyboardInterrupt

    analisadores = protetor.Analisadores()
    guarda = protetor.Protetor(lambda: analisadores.analisar, ao_decidir,
                               bloquear=not args.so_avisar, prazo=args.prazo)
    try:
        marcados = guarda.abrir()
    except OSError as erro:
        analisadores.fechar()
        print(f"{VERMELHO}Não deu para ligar o fanotify: {erro}{FIM}")
        return 1
    signal.signal(signal.SIGTERM, ao_sigterm)
    modo = "só avisando" if args.so_avisar else "bloqueando ameaças"
    print(f"{VERDE}Protegendo a execução em {', '.join(map(str, marcados))} ({modo}; prazo {args.prazo:g} s){FIM}")
    try:
        guarda.rodar()
    except KeyboardInterrupt:
        pass
    finally:
        analisadores.fechar()
    print(f"Protetor encerrado. {guarda.estatisticas}")
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
    print("Procurando bibliotecas injetadas, processos estranhos, persistência e comportamento...")
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
    print(f"{VERDE}Painel em {url}  (Ctrl+C para sair){FIM}")
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
    parser = argparse.ArgumentParser(prog="guardiao", description="Antivírus para Linux")
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
    p_varrer.add_argument("--agendada", action="store_true",
                          help="feita pelo timer: notifica o que achar e não falha por achar ameaça")
    p_varrer.set_defaults(func=cmd_varrer)

    p_h = sub.add_parser("historico", help="as últimas varreduras e o que acharam")
    p_h.add_argument("--achados", action="store_true", help="lista também o que cada uma achou")
    p_h.add_argument("--quantos", type=int, default=15, help="padrão: 15")
    p_h.set_defaults(func=cmd_historico)

    p_at = sub.add_parser("atualizar", help="baixa as bases de detecção mais recentes")
    modo_at = p_at.add_mutually_exclusive_group()
    modo_at.add_argument("--forcar", action="store_true", help="baixa de novo mesmo se estiver em dia")
    modo_at.add_argument("--status", action="store_true", help="só mostra a situação de cada base")
    p_at.set_defaults(func=cmd_atualizar)

    p_mon = sub.add_parser("monitorar", help="analisa em tempo real os arquivos que chegam")
    p_mon.add_argument("pastas", nargs="*", help="padrão: ~/Downloads")
    p_mon.add_argument("--isolar", action="store_true", help="move ameaças para a quarentena")
    p_mon.add_argument("--sem-comportamento", action="store_true",
                       help="não vigia o que os processos fazem (shells reversos, mineradores)")
    p_mon.set_defaults(func=cmd_monitorar)

    p_dev = sub.add_parser("dev", help="audita um projeto: pacotes, scripts de instalação, auto-execução")
    p_dev.add_argument("pasta", nargs="?", default=".", help="padrão: pasta atual")
    p_dev.add_argument("--todos", action="store_true", help="mostra também os achados informativos")
    p_dev.set_defaults(func=cmd_dev)

    p_c = sub.add_parser("cacar", help="caça persistência e rootkits já instalados no sistema")
    p_c.add_argument("--todos", action="store_true", help="mostra também os achados informativos")
    p_c.add_argument("--sem-pacotes", action="store_true", help="pula o dpkg --verify (o passo mais lento)")
    p_c.set_defaults(func=cmd_cacar)

    p_p = sub.add_parser("proteger", help="bloqueia ameaças antes de executarem (root, fanotify)")
    p_p.add_argument("--so-avisar", action="store_true", help="não bloqueia, só avisa")
    p_p.add_argument("--prazo", type=float, default=2.0,
                     help="segundos até liberar uma execução sem veredito (padrão: 2)")
    p_p.set_defaults(func=cmd_proteger)

    p_l = sub.add_parser("launcher", help="abre o painel no navegador")
    p_l.add_argument("--porta", type=int, default=8765)
    p_l.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    p_l.set_defaults(func=cmd_launcher)

    p_vt = sub.add_parser("virustotal", help="o que uns 70 antivírus acham de um arquivo (só o hash é enviado)")
    p_vt.add_argument("arquivo")
    p_vt.set_defaults(func=cmd_virustotal)

    p_q = sub.add_parser("quarentena", help="gerencia arquivos isolados")
    q_sub = p_q.add_subparsers(dest="acao", required=True)
    q_sub.add_parser("listar")
    q_sub.add_parser("restaurar").add_argument("id")
    p_q.set_defaults(func=cmd_quarentena)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
