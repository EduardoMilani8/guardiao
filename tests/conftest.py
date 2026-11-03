import pytest

from guardiao import cache


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    # Nenhum teste lê ou suja o cache de verdade em ~/.cache/guardiao.
    monkeypatch.setattr(cache, "PADRAO", tmp_path / "cache.sqlite")


@pytest.fixture(autouse=True)
def bases_isoladas(tmp_path, monkeypatch):
    # Nem as bases baixadas de verdade em ~/.local/share/guardiao/bases.
    from guardiao import bases
    monkeypatch.setattr(bases, "PASTA", tmp_path / "bases")
