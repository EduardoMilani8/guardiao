import os
import threading
import time
from pathlib import Path

import pytest

from guarnicao import protetor
from guarnicao.scanner import Resultado

# Marcador inofensivo que o analisador falso trata como ameaça.
MARCA = b"".join([b"ISTO-", b"E-AMEACA"])


def esperar(condicao, limite=3.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return False


class Cenario:
    """Um Protetor sem kernel: as respostas vão para uma lista."""

    def __init__(self, tmp_path: Path, bloquear=True, prazo=1.0, atraso=0.0, falhar=False):
        self.tmp = tmp_path
        self.respostas: list[tuple[int, bool]] = []
        self.avisos: list[protetor.Decisao] = []
        self.analises = 0
        self.liberar_analise = threading.Event()
        if not atraso:
            self.liberar_analise.set()

        def fabrica():
            def analisar(caminho: Path) -> Resultado:
                self.analises += 1
                self.liberar_analise.wait(5)
                if falhar:
                    raise ValueError("analisador quebrado")
                conteudo = caminho.read_bytes()
                return Resultado(caminho, "0" * 64, ameaca="Teste.Ameaca" if MARCA in conteudo else None)
            return analisar

        self.p = protetor.Protetor(fabrica, self.avisos.append, bloquear=bloquear, prazo=prazo,
                                   trabalhadores=2, enviar=lambda fd, ok: self.respostas.append((fd, ok)))
        self.p.iniciar()

    def arquivo(self, nome: str, conteudo: bytes) -> Path:
        caminho = self.tmp / nome
        caminho.write_bytes(conteudo)
        caminho.chmod(0o755)
        return caminho

    def executar(self, caminho: Path, pid: int = 4242) -> bool:
        """Simula um execve: o kernel abre o arquivo e pergunta."""
        fd = os.open(caminho, os.O_RDONLY)
        antes = len(self.respostas)
        self.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, fd, pid))
        assert esperar(lambda: len(self.respostas) > antes), "ninguém respondeu"
        resposta_fd, permitido = self.respostas[-1]
        assert resposta_fd == fd
        return permitido


@pytest.fixture
def cenario(tmp_path):
    criados = []

    def criar(**kw):
        c = Cenario(tmp_path, **kw)
        criados.append(c)
        return c
    yield criar
    for c in criados:
        c.liberar_analise.set()
        c.p.parar()


def test_le_eventos_colados_do_kernel():
    um = protetor.METADADOS.pack(24, 3, 0, 24, protetor.FAN_OPEN_EXEC_PERM, 7, 100)
    dois = protetor.METADADOS.pack(24, 3, 0, 24, protetor.FAN_OPEN_EXEC_PERM, 8, 200)
    assert [(e.fd, e.pid) for e in protetor.ler_eventos(um + dois)] == [(7, 100), (8, 200)]
    with pytest.raises(OSError):
        list(protetor.ler_eventos(protetor.METADADOS.pack(24, 2, 0, 24, 0, 7, 100)))


def test_pontos_de_montagem_um_por_disco(tmp_path):
    com_espaco = tmp_path / "meu disco"
    com_espaco.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(
        f"/dev/sda1 / ext4 rw 0 0\n"
        f"proc /proc proc rw 0 0\n"
        f"/dev/sda1 {tmp_path} ext4 rw 0 0\n"                                  # mesmo disco: repete
        f"tmpfs {str(com_espaco).replace(' ', chr(92) + '040')} tmpfs rw 0 0\n"
        f"sshfs /mnt/remoto fuse.sshfs rw 0 0\n"
    )
    pontos = protetor.pontos_de_montagem(mounts)
    assert Path("/") in pontos and Path("/proc") not in pontos and Path("/mnt/remoto") not in pontos
    # tmp_path está no mesmo dispositivo que "meu disco": entra só um dos dois. Se o
    # /tmp estiver no próprio / (sem tmpfs), o / já cobre os dois e não entra nenhum.
    mesmo_do_raiz = os.stat(tmp_path).st_dev == os.stat("/").st_dev
    assert len([p for p in pontos if p in (tmp_path, com_espaco)]) == (0 if mesmo_do_raiz else 1)


def st(uid=0, modo=0o100755):
    return os.stat_result((modo, 1, 1, 1, uid, 0, 10, 0, 0, 0))


def test_so_programas_do_sistema_sao_confiaveis():
    assert protetor.confiavel("/usr/bin/ls", st())
    assert protetor.confiavel("/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2", st())
    assert not protetor.confiavel("/usr/local/bin/ferramenta", st())
    assert not protetor.confiavel("/usr/bin/plantado", st(uid=1000))
    assert not protetor.confiavel("/usr/bin/gravavel", st(modo=0o100777))
    assert not protetor.confiavel("/home/voce/.local/bin/x", st())
    assert not protetor.confiavel("/usrx/bin/x", st())


def test_ameaca_e_bloqueada_e_o_limpo_passa(cenario):
    c = cenario()
    assert c.executar(c.arquivo("limpo", b"#!/bin/sh\necho oi\n")) is True
    ruim = c.arquivo("ruim", b"#!/bin/sh\n" + MARCA)
    assert c.executar(ruim) is False
    assert esperar(lambda: c.avisos)
    [aviso] = c.avisos
    assert (aviso.caminho, aviso.permitido, aviso.motivo) == (ruim, False, "ameaça")


def test_segunda_execucao_vem_do_cache_e_muda_se_o_arquivo_muda(cenario):
    c = cenario()
    ruim = c.arquivo("ruim", MARCA)
    assert c.executar(ruim) is False
    assert c.executar(ruim) is False
    assert c.analises == 1 and c.p.estatisticas["cache"] == 1
    ruim.write_bytes(b"#!/bin/sh\necho agora limpo\n")      # mudou: analisa de novo
    assert c.executar(ruim) is True and c.analises == 2


def test_prazo_libera_e_avisa_se_era_ameaca(cenario):
    c = cenario(prazo=0.2, atraso=True)
    ruim = c.arquivo("lento", MARCA)
    inicio = time.monotonic()
    assert c.executar(ruim) is True                     # o relógio liberou
    assert time.monotonic() - inicio < 2
    c.liberar_analise.set()
    assert esperar(lambda: c.avisos)
    assert (c.avisos[0].permitido, c.avisos[0].motivo) == (True, "prazo")
    assert c.executar(ruim) is False                    # da próxima vez, já se sabe


def test_modo_aviso_libera_mas_conta(cenario):
    c = cenario(bloquear=False)
    assert c.executar(c.arquivo("ruim", MARCA)) is True
    assert esperar(lambda: c.avisos) and c.avisos[0].motivo == "ameaça" and c.avisos[0].permitido


def test_analisador_quebrado_nao_trava_ninguem(cenario):
    c = cenario(falhar=True)
    assert c.executar(c.arquivo("qualquer", b"x")) is True
    assert esperar(lambda: c.avisos) and c.avisos[0].motivo == "erro"


def test_execucao_do_proprio_guarnicao_passa_sem_analise(cenario):
    c = cenario()
    assert c.executar(c.arquivo("ruim", MARCA), pid=os.getpid()) is True
    assert c.analises == 0


def test_aviso_lento_nao_segura_a_decisao(tmp_path):
    """ao_decidir pode demorar (notify-send): quem lê o kernel não espera por ele."""
    respostas, segurar = [], threading.Event()
    p = protetor.Protetor(
        lambda: (lambda caminho: Resultado(caminho, "0" * 64, ameaca="Teste.Ameaca")),
        lambda decisao: segurar.wait(5), trabalhadores=1, enviar=lambda fd, ok: respostas.append(ok))
    p.iniciar()
    try:
        alvo = tmp_path / "ruim"
        alvo.write_bytes(b"x")
        for _ in range(3):   # a 1ª analisa; as outras vêm do cache, na própria thread de leitura
            p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, os.open(alvo, os.O_RDONLY), 1))
        assert esperar(lambda: len(respostas) == 3) and respostas == [False] * 3
    finally:
        segurar.set()
        p.parar()


def test_execucoes_durante_a_analise_pegam_carona(cenario):
    """Um programa que se executa de novo enquanto ainda é analisado não espera dois prazos."""
    c = cenario(prazo=0.3, atraso=True)
    ruim = c.arquivo("reexecuta", MARCA)
    fds = [os.open(ruim, os.O_RDONLY) for _ in range(3)]
    inicio = time.monotonic()
    c.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, fds[0], 1))
    time.sleep(0.2)
    for fd in fds[1:]:
        c.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, fd, 2))
    assert esperar(lambda: len(c.respostas) == 3)
    assert time.monotonic() - inicio < 0.6          # todos no prazo do primeiro
    assert c.analises == 1
    c.liberar_analise.set()
    assert esperar(lambda: c.avisos)
    assert c.executar(ruim) is False


def test_carona_ainda_esperando_recebe_o_veredito(cenario):
    c = cenario(prazo=5)
    ruim = c.arquivo("ruim", MARCA)
    c.liberar_analise.clear()
    a, b = os.open(ruim, os.O_RDONLY), os.open(ruim, os.O_RDONLY)
    c.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, a, 1))
    c.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, b, 2))
    c.liberar_analise.set()
    assert esperar(lambda: len(c.respostas) == 2)
    assert sorted(c.respostas) == sorted([(a, False), (b, False)]) and c.analises == 1


def test_arquivo_apagado_durante_a_analise_ainda_e_julgado(cenario):
    """Malware que se apaga logo depois de executar não escapa: sobra o descritor do kernel."""
    c = cenario(prazo=5, atraso=True)
    ruim = c.arquivo("some", MARCA)
    fd = os.open(ruim, os.O_RDONLY)
    c.p.tratar(protetor.Evento(protetor.FAN_OPEN_EXEC_PERM, fd, 1))
    assert esperar(lambda: c.analises == 1)
    ruim.unlink()
    c.liberar_analise.set()
    assert esperar(lambda: c.respostas) and c.respostas == [(fd, False)]
    assert esperar(lambda: c.avisos) and c.avisos[0].motivo == "ameaça"
    assert c.avisos[0].caminho == ruim
