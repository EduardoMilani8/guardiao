import atexit
import os
import shutil
import tempfile

# Antes de importar o Guardião: os caminhos dele são calculados no import, e os
# processos da varredura em paralelo herdam estas variáveis. Assim nenhum teste
# enxerga as bases baixadas, o cache ou a quarentena de verdade desta máquina.
_TMP = tempfile.mkdtemp(prefix="guardiao-testes-")
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)
for variavel in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"):
    os.environ[variavel] = os.path.join(_TMP, variavel.lower())
# Nem o clamd de verdade, se estiver instalado: os testes usam um falso.
os.environ["GUARDIAO_CLAMD_SOCKET"] = os.path.join(_TMP, "sem-clamd.ctl")

import pytest  # noqa: E402

from guardiao import cache  # noqa: E402


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    # Nenhum teste lê ou suja o cache de verdade em ~/.cache/guardiao.
    monkeypatch.setattr(cache, "PADRAO", tmp_path / "cache.sqlite")


@pytest.fixture(autouse=True)
def bases_isoladas(tmp_path, monkeypatch):
    # Nem as bases baixadas de verdade em ~/.local/share/guardiao/bases.
    from guardiao import bases
    monkeypatch.setattr(bases, "PASTA", tmp_path / "bases")


@pytest.fixture(autouse=True)
def historico_isolado(tmp_path, monkeypatch):
    from guardiao import historico
    monkeypatch.setattr(historico, "ARQUIVO", tmp_path / "historico.jsonl")
