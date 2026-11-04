import os

import pytest

from guardiao import __main__ as cli
from guardiao import quarentena


def isolar_um(tmp_path):
    arquivo = tmp_path / "ruim.bin"
    arquivo.write_bytes(b"conteudo")
    pasta = tmp_path / "quarentena"
    return arquivo, pasta, quarentena.isolar(arquivo, "0" * 64, "teste", pasta)


@pytest.mark.parametrize("id_", ["0123456789ab", "../../etc/x", "ZZZ"])
def test_id_desconhecido_ou_invalido(tmp_path, id_):
    _, pasta, _ = isolar_um(tmp_path)
    with pytest.raises(quarentena.NaoEncontrado):
        quarentena.restaurar(id_, pasta)


def test_restaurar_duas_vezes(tmp_path):
    _, pasta, id_ = isolar_um(tmp_path)
    quarentena.restaurar(id_, pasta)
    with pytest.raises(quarentena.NaoEncontrado):
        quarentena.restaurar(id_, pasta)


def test_entrada_estragada_nao_esconde_as_outras(tmp_path):
    _, pasta, id_ = isolar_um(tmp_path)
    (pasta / "abcdefabcdef.json").write_text("{quebrado")
    assert [e["id"] for e in quarentena.listar(pasta)] == [id_]


def test_comando_explica_em_vez_de_quebrar(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["guardiao", "quarentena", "restaurar", "naoexiste"])
    assert cli.main() == 2
    assert "Nada com o id naoexiste" in capsys.readouterr().out
