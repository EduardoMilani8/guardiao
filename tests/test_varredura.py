import os
from pathlib import Path

import pytest

from guarnicao import quarentena, scanner, varredura

EICAR = "".join(["X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"])

MOUNTS = """\
sysfs /sys sysfs rw,nosuid 0 0
proc /proc proc rw,nosuid 0 0
/dev/nvme0n1p2 / ext4 rw,relatime 0 0
/dev/nvme0n1p1 /boot/efi vfat rw 0 0
tmpfs /dev/shm tmpfs rw 0 0
/dev/loop3 /snap/firefox/123 squashfs ro 0 0
/dev/sdb1 /media/eduardo/Meu\\040Pendrive vfat rw 0 0
servidor:/dados /mnt/rede nfs4 rw 0 0
"""


def resultados(itens):
    return [i for i in itens if isinstance(i, scanner.Resultado)]


def resumo(itens):
    return next(i for i in itens if isinstance(i, varredura.Resumo))


# --- raízes ------------------------------------------------------------------------

def test_completa_so_sistemas_de_arquivos_de_verdade():
    assert varredura.raizes_completa(mounts=MOUNTS) == [Path("/"), Path("/boot/efi"), Path("/dev/shm")]


def test_completa_com_externos_desescapa_o_nome():
    raizes = varredura.raizes_completa(incluir_externos=True, mounts=MOUNTS)
    assert Path("/media/eduardo/Meu Pendrive") in raizes
    assert Path("/mnt/rede") not in raizes   # rede continua de fora: nfs não está na lista


def test_sem_aninhadas(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "c").mkdir()
    raizes = varredura.sem_aninhadas([tmp_path / "a" / "b", tmp_path / "a", tmp_path / "c"])
    assert raizes == [tmp_path / "a", tmp_path / "c"]


def test_com_sudo_usa_a_casa_do_usuario(monkeypatch):
    import getpass
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", getpass.getuser())
    monkeypatch.setenv("HOME", "/root")
    casa = Path(os.path.expanduser("~" + getpass.getuser()))
    assert varredura.casa_real() == casa
    ex = varredura.carregar_exclusoes(Path("/nao/existe.toml"))
    assert str(casa / ".local/share/guarnicao/quarentena") in ex.pastas


# --- exclusões -------------------------------------------------------------------------

def test_config_toml(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('excluir_pastas = ["~/Vídeos"]\nexcluir_padroes = ["*.iso"]\ntamanho_maximo_mb = 1\n')
    ex = varredura.carregar_exclusoes(config)
    assert str(Path("~/Vídeos").expanduser().resolve()) in ex.pastas
    assert ex.ignora_nome("ubuntu.iso") and not ex.ignora_nome("foto.jpg")
    assert ex.tamanho_max == 1024 * 1024
    assert str(quarentena.PASTA_PADRAO) in ex.pastas   # os padrões continuam valendo


def test_exclusoes_e_limite_de_tamanho(tmp_path):
    (tmp_path / "pulada").mkdir()
    (tmp_path / "pulada" / "eicar.com").write_text(EICAR)
    (tmp_path / "imagem.iso").write_text(EICAR)
    (tmp_path / "grande.bin").write_bytes(b"\0" * 2048)
    (tmp_path / "ok.txt").write_text("oi")
    ex = varredura.Exclusoes(pastas=[str(tmp_path / "pulada")], padroes=["*.iso"], tamanho_max=1024)
    itens = list(varredura.executar([tmp_path], ex, usar_cache=False, processos=1))
    assert [r.caminho.name for r in resultados(itens)] == ["ok.txt"]
    assert resumo(itens).grandes == 1


def test_nao_segue_links(tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "eicar.com").write_text(EICAR)
    alvo = tmp_path / "alvo"
    alvo.mkdir()
    (alvo / "atalho").symlink_to(fora)
    itens = list(varredura.executar([alvo], varredura.Exclusoes(), usar_cache=False, processos=1))
    assert resultados(itens) == []


def test_raiz_pode_ser_um_arquivo(tmp_path):
    arquivo = tmp_path / "eicar.com"
    arquivo.write_text(EICAR)
    itens = list(varredura.executar([arquivo], varredura.Exclusoes(), usar_cache=False, processos=1))
    assert resumo(itens).ameacas == 1


# --- cache ---------------------------------------------------------------------------

def test_cache_pula_o_que_nao_mudou(tmp_path):
    pasta = tmp_path / "p"
    pasta.mkdir()
    (pasta / "limpo.txt").write_text("nada aqui")
    (pasta / "eicar.com").write_text(EICAR)
    ex = varredura.Exclusoes()

    primeira = resumo(list(varredura.executar([pasta], ex, processos=1)))
    segunda = resumo(list(varredura.executar([pasta], ex, processos=1)))
    assert (primeira.analisados, primeira.em_cache) == (2, 0)
    # O limpo foi pulado; a ameaça nunca entra no cache e é achada de novo.
    assert (segunda.analisados, segunda.em_cache, segunda.ameacas) == (1, 1, 1)


# --- paralelo ---------------------------------------------------------------------------

def test_processos_em_paralelo_acham_a_ameaca(tmp_path):
    for i in range(80):   # acima do mínimo para abrir processos
        (tmp_path / f"arquivo{i}.txt").write_text(f"conteúdo {i}")
    (tmp_path / "eicar.com").write_text(EICAR)
    itens = list(varredura.executar([tmp_path], varredura.Exclusoes(), usar_cache=False, processos=2))
    r = resumo(itens)
    assert (r.analisados, r.ameacas) == (81, 1)
    assert any(isinstance(i, varredura.Progresso) and i.fase == "analisando" for i in itens)


def workers_vivos() -> set[int]:
    # Com forkserver, os workers são filhos do processo forkserver, não deste:
    # multiprocessing.active_children() não os enxerga. O /proc enxerga.
    from multiprocessing import forkserver
    pai = forkserver._forkserver._forkserver_pid
    vivos = set()
    for d in Path("/proc").iterdir():
        try:
            estado, ppid = (d / "stat").read_text().rsplit(")", 1)[1].split()[:2]
        except (OSError, ValueError):
            continue
        if int(ppid) == pai and estado != "Z":
            vivos.add(int(d.name))
    return vivos


def test_parar_no_meio_encerra_os_processos(tmp_path):
    for i in range(200):
        (tmp_path / f"arquivo{i}.txt").write_text(f"conteúdo {i}")
    itens = varredura.executar([tmp_path], varredura.Exclusoes(), usar_cache=False, processos=2)
    next(i for i in itens if isinstance(i, scanner.Resultado))
    antes = workers_vivos()
    assert len(antes) == 2
    itens.close()   # o que o launcher faz quando a página aperta Parar
    assert not (workers_vivos() & antes)


@pytest.mark.skipif(os.geteuid() == 0, reason="root lê tudo")
def test_sem_permissao_e_contado(tmp_path):
    trancada = tmp_path / "trancada"
    trancada.mkdir()
    trancada.chmod(0)
    try:
        r = resumo(list(varredura.executar([tmp_path], varredura.Exclusoes(), usar_cache=False, processos=1)))
        assert r.sem_permissao == 1
    finally:
        trancada.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="root lê tudo")
def test_progresso_final_bate_com_o_resumo(tmp_path):
    (tmp_path / "ok.txt").write_text("oi")
    trancado = tmp_path / "trancado.txt"
    trancado.write_text("segredo")
    trancado.chmod(0)   # aparece na listagem, mas falha na leitura
    itens = list(varredura.executar([tmp_path], varredura.Exclusoes(), usar_cache=False, processos=1))
    ultimo = [i for i in itens if isinstance(i, varredura.Progresso)][-1]
    r = resumo(itens)
    assert ultimo.vistos == r.analisados + r.em_cache == 1
    assert ultimo.total == 2 and r.sem_permissao == 1


def test_disco_inteiro_nao_fica_na_memoria(tmp_path, monkeypatch):
    # 08/11/2026: listar o disco todo antes de analisar levou o processo a ~800 MB
    # (1,1 milhão de caminhos com stat). Agora analisa em lotes: o primeiro
    # arquivo é analisado antes de a listagem chegar ao fim.
    for i in range(10):
        (tmp_path / f"a{i:02}.txt").write_text(f"conteudo {i}")
    monkeypatch.setattr(varredura, "LOTE", 3)
    eventos = []
    percorrer = varredura.percorrer

    def percorrer_anotando(raiz, exclusoes, resumo):
        for caminho, st in percorrer(raiz, exclusoes, resumo):
            eventos.append(("lista", caminho))
            yield caminho, st
    monkeypatch.setattr(varredura, "percorrer", percorrer_anotando)
    itens = []
    for item in varredura.executar([tmp_path], varredura.Exclusoes(), usar_cache=False, processos=1):
        if isinstance(item, scanner.Resultado):
            eventos.append(("analisa", str(item.caminho)))
        itens.append(item)
    assert len(resultados(itens)) == 10 and resumo(itens).analisados == 10
    # A segunda passada (a que manda analisar) intercala: no máximo um lote listado à frente.
    segunda = eventos[[i for i, e in enumerate(eventos) if e[0] == "lista"][9] + 1:]
    primeira_analise = next(i for i, e in enumerate(segunda) if e[0] == "analisa")
    assert primeira_analise <= 3
