"""Camada ClamAV: milhões de assinaturas, mantidas em dia pelo freshclam.

Conversa com o clamd (o ClamAV que fica rodando em segundo plano) por um
socket Unix, usando o comando FILDES: em vez do caminho, manda o próprio
arquivo já aberto (SCM_RIGHTS). O clamd roda como o usuário `clamav`, que não
tem permissão para abrir a sua pasta pessoal; com o descritor recebido ele lê
o arquivo sem precisar dessa permissão e sem cópia do conteúdo.

Opcional, como o yara-x: sem o clamd instalado e rodando, a camada desliga.
Instalar: sudo apt install clamav clamav-daemon
"""

import os
import re
import socket
from datetime import datetime
from pathlib import Path

CONFIG_CLAMD = Path("/etc/clamav/clamd.conf")
SOCKETS_COMUNS = (Path("/var/run/clamav/clamd.ctl"), Path("/run/clamav/clamd.ctl"),
                  Path("/var/run/clamd.scan/clamd.sock"))
TEMPO_MAXIMO = 120   # segundos por arquivo (arquivos grandes demoram)


class ErroClamAV(OSError):
    pass


def encontrar_socket(config: Path | None = None) -> Path | None:
    if escolhido := os.environ.get("GUARDIAO_CLAMD_SOCKET"):
        return Path(escolhido)   # socket fora do padrão (e os testes, longe do clamd real)
    # O padrão é lido aqui, e não na assinatura: lá ele ficaria congelado no import.
    config = config or CONFIG_CLAMD
    try:
        if m := re.search(r"^LocalSocket\s+(\S+)", config.read_text(), re.MULTILINE):
            return Path(m.group(1))
    except OSError:
        pass
    return next((s for s in SOCKETS_COMUNS if s.exists()), None)


class ClamAV:
    def __init__(self, caminho_socket: Path):
        self.socket = caminho_socket

    def _conversar(self, comando: str, fd: int | None = None) -> str:
        # Prefixo "z": comando e resposta terminam em \0, sem ambiguidade com espaços.
        mensagem = f"z{comando}\0".encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(TEMPO_MAXIMO)
            s.connect(str(self.socket))
            s.sendall(mensagem)
            if fd is not None:
                # O descritor vai num pacote próprio, depois do comando, com um
                # byte qualquer: colado no comando, o clamd o rejeita.
                socket.send_fds(s, [b"\0"], [fd])
            resposta = b""
            while not resposta.endswith(b"\0"):
                bloco = s.recv(4096)
                if not bloco:
                    break
                resposta += bloco
        return resposta.rstrip(b"\0").decode(errors="replace")

    def ping(self) -> bool:
        try:
            return self._conversar("PING") == "PONG"
        except OSError:
            return False

    def versao(self) -> tuple[str, int | None, datetime | None]:
        """Ex.: ("ClamAV 1.4.3", 27811, data das assinaturas)."""
        # O VERSION vem desligado em alguns clamd.conf (EnableVersionCommand false,
        # o padrão no Ubuntu 26.04); o VERSIONCOMMANDS responde o mesmo e mais
        # a lista de comandos: "ClamAV 1.5.4/28173/Tue Nov  3 03:27:52 2026| COMMANDS: ..."
        texto = self._conversar("VERSIONCOMMANDS").partition("|")[0]
        motor, _, resto = texto.partition("/")
        numero, _, data = resto.partition("/")
        try:
            quando = datetime.strptime(" ".join(data.split()), "%a %b %d %H:%M:%S %Y")
        except ValueError:
            quando = None
        return motor, int(numero) if numero.isdigit() else None, quando

    def verificar(self, caminho: Path) -> str | None:
        """Nome da ameaça, ou None se o ClamAV não achou nada."""
        # O_NOFOLLOW: um link plantado numa pasta varrida não leva a outro arquivo.
        # A exceção é o /proc/<pid>/fd do protetor, que é um link por natureza.
        pelo_fd = re.fullmatch(r"/proc/\d+/fd/\d+", str(caminho)) is not None
        fd = os.open(caminho, os.O_RDONLY | (0 if pelo_fd else os.O_NOFOLLOW))
        try:
            resposta = self._conversar("FILDES", fd)
        finally:
            os.close(fd)
        # "fd[10]: OK" · "fd[10]: Unix.Trojan.Mirai-9983 FOUND" · "fd[10]: ... ERROR"
        _, _, veredito = resposta.partition(": ")
        if veredito == "OK":
            return None
        if veredito.endswith(" FOUND"):
            return veredito.removesuffix(" FOUND")
        raise ErroClamAV(f"ClamAV: {veredito or resposta or 'sem resposta'}")


def conectar() -> ClamAV | None:
    """O clamd desta máquina, se estiver instalado e respondendo."""
    caminho = encontrar_socket()
    if caminho is None:
        return None
    cliente = ClamAV(caminho)
    return cliente if cliente.ping() else None
