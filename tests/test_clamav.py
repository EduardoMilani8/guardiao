import os
import socket
import threading

import pytest

from guardiao import assinaturas, clamav, scanner

from .test_guardiao import EICAR


class ClamdFalso:
    """Fala o protocolo do clamd num socket Unix. Recebe o arquivo como o real:
    um descritor aberto, via SCM_RIGHTS, e lê o conteúdo por ele."""

    def __init__(self, caminho):
        self.caminho = caminho
        self.servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.servidor.bind(str(caminho))
        self.servidor.listen()
        self.leu_por_fd = 0
        threading.Thread(target=self._atender, daemon=True).start()

    def _atender(self):
        while True:
            try:
                conexao, _ = self.servidor.accept()
            except OSError:
                return
            with conexao:
                mensagem, fds, _, _ = socket.recv_fds(conexao, 1024, 1)
                comando = mensagem.rstrip(b"\0").decode()
                if comando == "zPING":
                    resposta = "PONG"
                elif comando == "zVERSION":
                    resposta = "ClamAV 1.4.3/27811/Tue Nov  3 08:00:00 2026"
                elif comando == "zFILDES" and fds:
                    with os.fdopen(fds[0], "rb") as f:
                        conteudo = f.read()
                    self.leu_por_fd += 1
                    if b"EICAR" in conteudo:
                        resposta = "fd[10]: Win.Test.EICAR_HDB-1 FOUND"
                    elif b"corrompido" in conteudo:
                        resposta = "fd[10]: Can't read file ERROR"
                    else:
                        resposta = "fd[10]: OK"
                else:
                    resposta = "UNKNOWN COMMAND"
                conexao.sendall(resposta.encode() + b"\0")

    def fechar(self):
        self.servidor.close()


@pytest.fixture
def clamd(tmp_path, monkeypatch):
    falso = ClamdFalso(tmp_path / "clamd.ctl")
    monkeypatch.setattr(clamav, "CONFIG_CLAMD", tmp_path / "nao-existe.conf")
    monkeypatch.setattr(clamav, "SOCKETS_COMUNS", (falso.caminho,))
    yield falso
    falso.fechar()


def test_conecta_e_le_a_versao(clamd):
    cliente = clamav.conectar()
    motor, numero, quando = cliente.versao()
    assert (motor, numero, quando.day) == ("ClamAV 1.4.3", 27811, 3)


def test_acha_socket_no_clamd_conf(tmp_path):
    conf = tmp_path / "clamd.conf"
    conf.write_text("# comentário\nLocalSocket /run/outro/clamd.sock\nUser clamav\n")
    assert str(clamav.encontrar_socket(conf)) == "/run/outro/clamd.sock"


def test_sem_clamd_a_camada_desliga(tmp_path, monkeypatch):
    monkeypatch.setattr(clamav, "CONFIG_CLAMD", tmp_path / "nao-existe.conf")
    monkeypatch.setattr(clamav, "SOCKETS_COMUNS", (tmp_path / "nao-existe.ctl",))
    assert clamav.conectar() is None


def test_ameaca_do_clamav_e_lida_pelo_descritor(tmp_path, clamd):
    arquivo = tmp_path / "anexo.pdf"
    arquivo.write_bytes(b"%PDF " + EICAR)
    arquivo.chmod(0o600)   # o clamd real (usuário clamav) não conseguiria abrir pelo caminho
    r = scanner.analisar(arquivo, {}, None, clamav.conectar())
    assert r.ameaca == "Win.Test.EICAR_HDB-1 (ClamAV)" and r.camada == "clamav"
    assert clamd.leu_por_fd == 1


def test_assinatura_local_vem_antes_do_clamav(tmp_path, clamd):
    arquivo = tmp_path / "eicar.com"
    arquivo.write_bytes(EICAR)
    r = scanner.analisar(arquivo, assinaturas.carregar(), None, clamav.conectar())
    assert r.camada == "hash" and clamd.leu_por_fd == 0   # nem precisou perguntar


def test_erro_do_clamav_nao_derruba_as_outras_camadas(tmp_path, clamd):
    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"corrompido")
    r = scanner.analisar(arquivo, {}, None, clamav.conectar())
    assert not r.infectado and any("ClamAV não respondeu" in m for m in r.motivos)


def test_nao_segue_link_simbolico(tmp_path, clamd):
    alvo = tmp_path / "alvo"
    alvo.write_bytes(b"conteudo")
    (tmp_path / "atalho").symlink_to(alvo)
    with pytest.raises(OSError):
        clamav.conectar().verificar(tmp_path / "atalho")


def test_avisa_assinaturas_velhas(clamd):
    from datetime import datetime

    from guardiao import bases
    agora = datetime(2026, 11, 10).timestamp()   # a versão falsa é de 3/11
    assert bases._aviso_clamav(agora) == ["clamav: assinaturas de 6 dia(s) atrás (o freshclam está rodando?)"]
    assert bases._aviso_clamav(datetime(2026, 11, 3, 20).timestamp()) == []
