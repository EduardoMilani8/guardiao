import pytest

import guarnicao


def test_python_antigo_para_com_mensagem_clara():
    # Ubuntu 22.04 vem com 3.10: sem isso, o erro era um traceback do tomllib no journal.
    with pytest.raises(SystemExit) as saida:
        guarnicao.conferir_python((3, 10, 12))
    assert "3.11" in str(saida.value) and "3.10" in str(saida.value)


def test_python_novo_passa():
    guarnicao.conferir_python((3, 11, 0))
    guarnicao.conferir_python((3, 14, 4))
