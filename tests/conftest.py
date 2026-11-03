import pytest

from guardiao import cache


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    # Nenhum teste lê ou suja o cache de verdade em ~/.cache/guardiao.
    monkeypatch.setattr(cache, "PADRAO", tmp_path / "cache.sqlite")
