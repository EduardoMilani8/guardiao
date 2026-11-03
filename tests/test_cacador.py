from pathlib import Path

import pytest

from guardiao import cacador


@pytest.fixture
def pacotes(tmp_path):
    """Um dpkg falso que diz ter instalado /usr/lib/x86_64-linux-gnu/libc.so.6 e /bin/ls."""
    info = tmp_path / "dpkg-info"
    info.mkdir()
    (info / "libc6.list").write_text("/.\n/usr\n/usr/lib/x86_64-linux-gnu/libc.so.6\n")
    (info / "coreutils.list").write_text("/bin/ls\n")
    return cacador.Pacotes(info)


@pytest.fixture
def tmp_nao_e_temporaria(monkeypatch):
    # O tmp_path do pytest fica em /tmp: sem isto, a regra da pasta temporária responderia antes.
    monkeypatch.setattr(cacador, "PASTAS_TEMPORARIAS", ("/dev/shm/",))


def processo(proc: Path, pid: int, nome: str, ambiente: dict[str, str] | None = None,
             exe: str | None = None) -> Path:
    pasta = proc / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "comm").write_text(nome + "\n")
    (pasta / "environ").write_bytes(b"".join(f"{k}={v}".encode() + b"\0" for k, v in (ambiente or {}).items()))
    if exe:
        (pasta / "exe").symlink_to(exe)
    return pasta


# --- pacotes ----------------------------------------------------------------

def test_pacotes_entende_o_usrmerge(pacotes):
    # O pacote registrou /usr/lib/... e /bin/ls; os dois nomes de cada um valem.
    assert pacotes.dono("/usr/lib/x86_64-linux-gnu/libc.so.6")
    assert pacotes.dono("/lib/x86_64-linux-gnu/libc.so.6")
    assert pacotes.dono("/usr/bin/ls")
    assert not pacotes.dono("/usr/lib/libmalvada.so")
    assert not pacotes.dono("/usrlib/x")


# --- /etc/ld.so.preload -----------------------------------------------------

def test_preload_inexistente_nao_e_achado(tmp_path, pacotes):
    assert list(cacador.preload(pacotes, tmp_path / "ld.so.preload")) == []


def test_preload_vazio_e_so_informativo(tmp_path, pacotes):
    arquivo = tmp_path / "ld.so.preload"
    arquivo.write_text("# nada aqui\n\n")
    [achado] = cacador.preload(pacotes, arquivo)
    assert achado.gravidade == "info"


def test_preload_de_biblioteca_fora_de_pacote_e_alto(tmp_path, pacotes, tmp_nao_e_temporaria):
    lib = tmp_path / "libprocesshider.so"
    lib.write_bytes(b"\x7fELF")
    arquivo = tmp_path / "ld.so.preload"
    arquivo.write_text(f"{lib}\n")
    [achado] = cacador.preload(pacotes, arquivo)
    assert achado.gravidade == "alta"
    assert achado.arquivo == lib
    assert "nenhum pacote" in achado.mensagem


def test_preload_de_pasta_temporaria_e_alto_mesmo_sumido(tmp_path, pacotes):
    arquivo = tmp_path / "ld.so.preload"
    arquivo.write_text("/dev/shm/.x/lib.so /usr/lib/x86_64-linux-gnu/libc.so.6\n")
    achados = {str(a.arquivo): a.gravidade for a in cacador.preload(pacotes, arquivo)}
    assert achados["/dev/shm/.x/lib.so"] == "alta"


# --- LD_PRELOAD nos processos -----------------------------------------------

def test_ld_preload_agrupa_por_biblioteca(tmp_path, pacotes):
    proc = tmp_path / "proc"
    for pid in (10, 11, 12):
        processo(proc, pid, f"bash{pid}", {"LD_PRELOAD": "/tmp/.ICE-unix/libz.so", "HOME": "/root"})
    processo(proc, 20, "firefox", {"HOME": "/home/x"})
    (proc / "self").mkdir()   # entradas que não são processos
    [achado] = cacador.ld_preload_em_processos(pacotes, proc)
    assert achado.gravidade == "alta"
    assert "bash10 (10)" in achado.mensagem and "bash12 (12)" in achado.mensagem


def test_ld_preload_do_snap_e_ignorado(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 30, "snapd-desktop-i",
             {"LD_PRELOAD": ":/snap/snapd-desktop-integration/391/gnome-platform/$LIB/bindtextdomain.so"})
    assert list(cacador.ld_preload_em_processos(pacotes, proc)) == []


def test_ld_preload_de_pacote_e_informativo(tmp_path, pacotes, monkeypatch):
    proc = tmp_path / "proc"
    processo(proc, 40, "app", {"LD_PRELOAD": "/usr/lib/x86_64-linux-gnu/libc.so.6"})
    monkeypatch.setattr(cacador.os.path, "exists", lambda _: True)
    [achado] = cacador.ld_preload_em_processos(pacotes, proc)
    assert achado.gravidade == "info"


def test_processo_ilegivel_e_pulado(tmp_path, pacotes):
    proc = tmp_path / "proc"
    pasta = processo(proc, 50, "sshd")
    (pasta / "environ").unlink()   # como um processo de outro usuário sem root
    assert list(cacador.ld_preload_em_processos(pacotes, proc)) == []


# --- processos --------------------------------------------------------------

def julgar_nada(_caminho):
    return None


def test_processo_de_pasta_temporaria_e_alto(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 60, "kdevtmpfsi", exe="/tmp/.X25-unix/kdevtmpfsi")
    processo(proc, 61, "kdevtmpfsi", exe="/tmp/.X25-unix/kdevtmpfsi")
    processo(proc, 62, "bash", exe="/usr/bin/bash")
    [achado] = cacador.processos(julgar_nada, pacotes, proc)
    assert achado.gravidade == "alta"
    assert achado.arquivo == Path("/tmp/.X25-unix/kdevtmpfsi")
    assert "(60)" in achado.mensagem and "(61)" in achado.mensagem


def test_processo_da_memoria_e_alto_exceto_runc(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 70, "x", exe="/memfd:payload (deleted)")
    processo(proc, 71, "runc:[2:INIT]", exe="/memfd:runc_cloned:/proc/self/exe (deleted)")
    [achado] = cacador.processos(julgar_nada, pacotes, proc)
    assert achado.gravidade == "alta" and "memfd" in achado.mensagem


def test_executavel_apagado(tmp_path, pacotes, tmp_nao_e_temporaria):
    proc = tmp_path / "proc"
    atualizado = tmp_path / "bin" / "editor"
    atualizado.parent.mkdir()
    atualizado.write_text("versão nova")
    processo(proc, 80, "editor", exe=f"{atualizado} (deleted)")       # o apt trocou o arquivo
    processo(proc, 81, "ls", exe="/usr/bin/ls (deleted)")              # de pacote, sumiu
    processo(proc, 82, "sumiu", exe="/home/x/.cache/sumiu (deleted)")  # sumiu de vez
    gravidades = {a.arquivo.name: a.gravidade for a in cacador.processos(julgar_nada, pacotes, proc)}
    assert gravidades == {"editor": "info", "ls": "info", "sumiu": "media"}


def test_processo_sem_permissao_e_pulado(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 90, "sshd")   # sem o link exe, como um processo de root visto sem root
    assert list(cacador.processos(julgar_nada, pacotes, proc)) == []


def test_executavel_do_processo_passa_pelo_scanner(tmp_path, pacotes):
    from .test_guardiao import EICAR
    binario = tmp_path / "minerador"
    binario.write_bytes(EICAR)
    proc = tmp_path / "proc"
    processo(proc, 100, "minerador", exe=str(binario))
    banco = {__import__("hashlib").sha256(EICAR).hexdigest(): "EICAR-Test-File"}
    [achado] = cacador.processos(cacador.juiz(banco), pacotes, proc)
    assert achado.gravidade == "alta"
    assert achado.mensagem.startswith("EICAR-Test-File")


def test_informativo_nao_e_julgado(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 110, "ls", exe="/usr/bin/ls (deleted)")
    julgados = []
    list(cacador.processos(lambda c: julgados.append(c), pacotes, proc))
    assert julgados == []
