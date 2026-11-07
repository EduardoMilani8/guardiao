"""As regras compiladas uma vez no forkserver e divididas pelos processos filhos."""

from pathlib import Path

from guarnicao import regras_yara


def test_carregar_usa_as_regras_compartilhadas_se_as_fontes_batem(monkeypatch):
    regras_yara.preparar_compartilhadas()
    monkeypatch.setattr(regras_yara, "_compilar", lambda *a: (_ for _ in ()).throw(AssertionError("compilou")))
    assert regras_yara.carregar() is not None


def test_fontes_novas_compilam_de_novo(monkeypatch, tmp_path):
    regras_yara.preparar_compartilhadas()
    nova = tmp_path / "base" / "versoes" / "v2" / "regras.yar"
    nova.parent.mkdir(parents=True)
    nova.write_text("rule nova { condition: false }")
    monkeypatch.setattr(regras_yara, "regras_das_bases", lambda: [nova])
    compilou = []
    original = regras_yara._compilar
    monkeypatch.setattr(regras_yara, "_compilar", lambda *a: compilou.append(a) or original(*a))
    assert regras_yara.carregar() is not None and compilou


def test_outra_pasta_nao_usa_as_compartilhadas(monkeypatch, tmp_path):
    regras_yara.preparar_compartilhadas()
    (tmp_path / "x.yar").write_text("rule x { condition: false }")
    compilou = []
    original = regras_yara._compilar
    monkeypatch.setattr(regras_yara, "_compilar", lambda *a: compilou.append(a) or original(*a))
    regras_yara.carregar(tmp_path)
    assert compilou


def test_contexto_carrega_as_regras_no_forkserver():
    ctx = regras_yara.contexto()
    from multiprocessing import forkserver
    assert "guarnicao.regras_compartilhadas" in forkserver._forkserver._preload_modules
    assert ctx.get_start_method() == "forkserver"


def test_contexto_renova_o_forkserver_quando_a_base_muda(monkeypatch, tmp_path):
    from multiprocessing import forkserver
    ctx = regras_yara.contexto()
    with ctx.Pool(1) as pool:
        pool.apply(int)
    antes = forkserver._forkserver._forkserver_pid
    nova = tmp_path / "regras.yar"
    nova.write_text("rule n { condition: false }")
    monkeypatch.setattr(regras_yara, "regras_das_bases", lambda: [Path(nova)])
    assert regras_yara.base_mudou()
    ctx = regras_yara.contexto()
    with ctx.Pool(1) as pool:
        pool.apply(int)
    assert forkserver._forkserver._forkserver_pid != antes
    assert not regras_yara.base_mudou()
