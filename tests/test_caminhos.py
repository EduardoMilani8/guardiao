"""A troca de nome de Guardião para Guarnição não pode perder nada de quem já usava."""

from pathlib import Path

from guarnicao import caminhos


def pastas_antigas(casa: Path) -> dict[str, Path]:
    lugares = {"config": casa / ".config", "dados": casa / ".local" / "share", "cache": casa / ".cache"}
    for lugar in lugares.values():
        (lugar / "guardiao").mkdir(parents=True)
    (lugares["config"] / "guardiao" / "config.toml").write_text("[virustotal]\n")
    (lugares["dados"] / "guardiao" / "historico.jsonl").write_text("{}\n")
    return lugares


def test_migra_as_tres_pastas_e_deixa_atalho(tmp_path):
    lugares = pastas_antigas(tmp_path)
    movidas = caminhos.migrar(casa=tmp_path, ambiente={})
    assert sorted(movidas) == sorted(l / "guarnicao" for l in lugares.values())
    assert (lugares["config"] / "guarnicao" / "config.toml").read_text() == "[virustotal]\n"
    assert (lugares["dados"] / "guarnicao" / "historico.jsonl").exists()
    # Um serviço antigo ainda rodando continua achando os arquivos pelo nome velho.
    atalho = lugares["dados"] / "guardiao"
    assert atalho.is_symlink() and (atalho / "historico.jsonl").read_text() == "{}\n"


def test_rodar_de_novo_nao_faz_nada(tmp_path):
    pastas_antigas(tmp_path)
    caminhos.migrar(casa=tmp_path, ambiente={})
    assert caminhos.migrar(casa=tmp_path, ambiente={}) == []


def test_nao_mexe_quando_a_nova_ja_existe(tmp_path):
    lugares = pastas_antigas(tmp_path)
    (lugares["config"] / "guarnicao").mkdir()
    caminhos.migrar(casa=tmp_path, ambiente={})
    assert (lugares["config"] / "guardiao" / "config.toml").exists()   # a antiga fica intacta
    assert not (lugares["config"] / "guarnicao" / "config.toml").exists()


def test_respeita_xdg(tmp_path):
    dados = tmp_path / "outro-lugar"
    (dados / "guardiao" / "quarentena").mkdir(parents=True)
    caminhos.migrar(casa=tmp_path / "casa", ambiente={"XDG_DATA_HOME": str(dados)})
    assert (dados / "guarnicao" / "quarentena").is_dir()


def test_sem_nada_antigo_nao_cria_nada(tmp_path):
    assert caminhos.migrar(casa=tmp_path, ambiente={}) == []
    assert list(tmp_path.iterdir()) == []


def test_variavel_antiga_ainda_vale(monkeypatch):
    monkeypatch.delenv("GUARNICAO_TESTE", raising=False)
    monkeypatch.setenv("GUARDIAO_TESTE", "velha")
    assert caminhos.variavel("TESTE") == "velha"
    monkeypatch.setenv("GUARNICAO_TESTE", "nova")
    assert caminhos.variavel("TESTE") == "nova"
