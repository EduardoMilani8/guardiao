import queue

import pytest

pytest.importorskip("watchdog")

from guardiao import assinaturas, monitor

from .test_guardiao import EICAR
from .test_yara import REVERSE_SHELL

ESPERA = 5  # segundos


@pytest.fixture
def vigiar(tmp_path):
    """Inicia um Monitor (com YARA) em tmp_path e devolve a fila de resultados."""
    resultados: queue.Queue = queue.Queue()
    m = monitor.Monitor([tmp_path], assinaturas.carregar(), resultados.put)
    m.iniciar()
    yield resultados
    m.parar()


def test_detecta_arquivo_escrito_direto(tmp_path, vigiar):
    (tmp_path / "teste.com").write_bytes(EICAR)
    resultado = vigiar.get(timeout=ESPERA)
    assert resultado.ameaca == "EICAR-Test-File"


def test_espera_download_terminar(tmp_path, vigiar):
    """Simula o navegador: baixa como .part e renomeia ao terminar."""
    parcial = tmp_path / "instalador.com.part"
    parcial.write_bytes(EICAR)
    parcial.rename(tmp_path / "instalador.com")

    resultado = vigiar.get(timeout=ESPERA)
    assert resultado.caminho.name == "instalador.com"
    assert resultado.infectado
    with pytest.raises(queue.Empty):   # o .part nunca é analisado
        vigiar.get(timeout=0.5)


def test_arquivo_limpo_tambem_e_relatado(tmp_path, vigiar):
    (tmp_path / "notas.txt").write_text("nada de mais")
    resultado = vigiar.get(timeout=ESPERA)
    assert not resultado.infectado and not resultado.suspeito


def test_yara_funciona_na_thread_do_monitor(tmp_path, vigiar):
    """Regressão: o Scanner do YARA-X não pode ser criado numa thread e usado em outra."""
    pytest.importorskip("yara_x")
    (tmp_path / "atualizar.sh").write_text(REVERSE_SHELL)
    assert vigiar.get(timeout=ESPERA).ameaca == "ReverseShell_DevTcp (YARA)"


def test_detecta_em_subpasta(tmp_path, vigiar):
    sub = tmp_path / "projeto-extraido"
    sub.mkdir()
    (sub / "teste.com").write_bytes(EICAR)
    assert vigiar.get(timeout=ESPERA).infectado
