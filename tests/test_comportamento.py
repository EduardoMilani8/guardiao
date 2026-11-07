from pathlib import Path

import pytest

from guarnicao import comportamento

TCP_CABECALHO = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"


def linha_tcp(remoto: str, estado: str, inode: int) -> str:
    return f"   0: 0100007F:9C40 {remoto} {estado} 00000000:00000000 00:00000000 00000000  1000        0 {inode}\n"


class ProcFalso:
    """Um /proc mínimo: stat, exe, fd/ e net/tcp."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        (raiz / "net").mkdir(parents=True)
        self.tcp = [TCP_CABECALHO]

    def conexao(self, remoto: str, inode: int, estado: str = "01") -> str:
        self.tcp.append(linha_tcp(remoto, estado, inode))
        (self.raiz / "net" / "tcp").write_text("".join(self.tcp))
        return f"socket:[{inode}]"

    def processo(self, pid: int, exe: str, ppid: int = 1, cpu: int = 0, inicio: int = 1000,
                 fds: dict[int, str] | None = None) -> None:
        pasta = self.raiz / str(pid)
        (pasta / "fd").mkdir(parents=True, exist_ok=True)
        nome = Path(exe).name[:15]
        # Campos depois do ")": estado, ppid, ... utime (14º) e stime (15º), starttime (22º).
        campos = ["S", str(ppid)] + ["0"] * 9 + [str(cpu), "0"] + ["0"] * 6 + [str(inicio)] + ["0"] * 10
        (pasta / "stat").write_text(f"{pid} ({nome}) {' '.join(campos)}\n")
        if (pasta / "exe").is_symlink():
            (pasta / "exe").unlink()
        (pasta / "exe").symlink_to(exe)
        for fd, alvo in (fds or {}).items():
            (pasta / "fd" / str(fd)).symlink_to(alvo)


@pytest.fixture
def proc(tmp_path):
    return ProcFalso(tmp_path / "proc")


# 203.0.113.7:4444 em hexadecimal little-endian, como o kernel escreve.
ATACANTE = "077100CB:115C"
LOCAL_47001 = "0100007F:B799"
POOL_3333 = "077100CB:0D05"


def test_endereco_do_kernel():
    assert comportamento._endereco("0100007F:0016") == ("127.0.0.1", 22)
    assert comportamento._endereco(ATACANTE) == ("203.0.113.7", 4444)
    assert comportamento._endereco("0000000000000000FFFF00000100007F:1F90") == ("127.0.0.1", 8080)
    assert comportamento._endereco("00000000000000000000000001000000:0050") == ("::1", 80)


def test_shell_com_entrada_e_saida_na_rede_e_alto(proc):
    sock = proc.conexao(ATACANTE, 555)
    proc.processo(100, "/usr/bin/bash", fds={0: sock, 1: sock, 2: sock})
    [alerta] = comportamento.shells_reversos(comportamento.fotografar(proc.raiz))
    assert (alerta.tipo, alerta.gravidade) == ("shell reverso", "alta")
    assert "203.0.113.7:4444" in alerta.mensagem and "kill 100" in alerta.mensagem


def test_shell_reverso_local_e_so_atencao(proc):
    sock = proc.conexao(LOCAL_47001, 556)
    proc.processo(101, "/usr/bin/python3.14", fds={0: sock, 1: sock})
    [alerta] = comportamento.shells_reversos(comportamento.fotografar(proc.raiz))
    assert alerta.gravidade == "media" and "python" in alerta.mensagem


def test_shell_com_pty_aberto_pelo_socat(proc):
    sock = proc.conexao(ATACANTE, 557)
    proc.processo(200, "/usr/bin/socat1", fds={3: sock})
    proc.processo(201, "/usr/bin/bash", ppid=200, fds={0: "/dev/pts/5", 1: "/dev/pts/5"})
    [alerta] = comportamento.shells_reversos(comportamento.fotografar(proc.raiz))
    assert alerta.processo.pid == 201 and "aberto pelo socat (200)" in alerta.mensagem


def test_terminal_comum_e_servicos_nao_disparam(proc):
    proc.processo(300, "/usr/bin/zsh", fds={0: "/dev/pts/1", 1: "/dev/pts/1"})
    proc.processo(301, "/usr/bin/bash", fds={1: "socket:[999]"})   # socket Unix (journal): fora das tabelas TCP
    sock = proc.conexao("077100CB:01BB", 558)
    proc.processo(302, "/usr/lib/firefox/firefox", fds={40: sock})   # navegador falando com a rede
    assert list(comportamento.shells_reversos(comportamento.fotografar(proc.raiz))) == []


def test_minerador_precisa_de_cpu_e_porta_de_pool(proc, monkeypatch):
    monkeypatch.setattr(comportamento, "TICKS", 100)
    pool = proc.conexao(POOL_3333, 600)
    web = proc.conexao("077100CB:01BB", 601)
    proc.processo(400, "/tmp/.x/kworker", cpu=0, fds={5: pool})
    proc.processo(401, "/usr/bin/gcc", cpu=0, fds={})              # CPU alta sem pool: compilador
    proc.processo(402, "/opt/app/sincroniza", cpu=0, fds={5: web})
    proc.processo(403, "/opt/app/ocioso", cpu=0, fds={5: proc.conexao(POOL_3333, 602)})   # pool sem CPU
    antes = comportamento.fotografar(proc.raiz)
    proc.processo(400, "/tmp/.x/kworker", cpu=290)   # 2,9 s de CPU em 3 s
    proc.processo(401, "/usr/bin/gcc", cpu=300)
    proc.processo(402, "/opt/app/sincroniza", cpu=300)
    proc.processo(403, "/opt/app/ocioso", cpu=5)
    depois = comportamento.fotografar(proc.raiz)
    [alerta] = comportamento.mineradores(antes, depois, 3.0)
    assert alerta.processo.pid == 400 and alerta.gravidade == "alta"
    assert "97% de um núcleo" in alerta.mensagem


def test_pid_reaproveitado_nao_vira_minerador(proc, monkeypatch):
    monkeypatch.setattr(comportamento, "TICKS", 100)
    pool = proc.conexao(POOL_3333, 700)
    proc.processo(500, "/usr/bin/x", cpu=0, inicio=1000, fds={5: pool})
    antes = comportamento.fotografar(proc.raiz)
    proc.processo(500, "/usr/bin/x", cpu=900, inicio=2000)   # outro processo, mesmo pid
    assert list(comportamento.mineradores(antes, comportamento.fotografar(proc.raiz), 3.0)) == []


def test_vigia_avisa_uma_vez_por_processo(proc):
    sock = proc.conexao(ATACANTE, 800)
    proc.processo(600, "/usr/bin/bash", fds={0: sock, 1: sock})
    alertas = []
    with comportamento.Vigia(alertas.append, intervalo=0.05, proc=proc.raiz):
        __import__("time").sleep(0.4)
    assert [a.processo.pid for a in alertas] == [600]
