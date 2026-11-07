import sys

import pytest

from guarnicao import __main__ as cli
from guarnicao import notificacao, quarentena, scanner, trancar

# A quarentena já fica numa pasta temporária: o conftest aponta XDG_DATA_HOME para lá.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def test_tranca_o_mesmo_arquivo(tmp_path):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    id_ = trancar.trancar(str(arq), scanner.calcular_sha256(arq), "EICAR", "hash")
    assert not arq.exists() and id_ in {e["id"] for e in quarentena.listar()}


def test_recusa_arquivo_que_mudou(tmp_path):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    sha = scanner.calcular_sha256(arq)
    arq.write_bytes(b"outra coisa")
    with pytest.raises(trancar.Recusa) as e:
        trancar.trancar(str(arq), sha)
    assert e.value.status == 409 and arq.exists()


def test_recusa_link_e_arquivo_sumido(tmp_path):
    alvo = tmp_path / "alvo"
    alvo.write_bytes(EICAR)
    link = tmp_path / "link"
    link.symlink_to(alvo)
    for caminho in (link, tmp_path / "nao-existe"):
        with pytest.raises(trancar.Recusa) as e:
            trancar.trancar(str(caminho), "0" * 64)
        assert e.value.status == 410
    assert alvo.exists()


def test_cli_tranca_e_confirma_com_desfazer(tmp_path, monkeypatch):
    arq = tmp_path / "ruim.com"
    arq.write_bytes(EICAR)
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["guarnicao", "quarentena", "trancar", str(arq),
                                      "--sha256", scanner.calcular_sha256(arq)])
    assert cli.main() == 0
    [((titulo, corpo), opcoes)] = avisos
    assert titulo == "Trancado na quarentena" and corpo.splitlines()[0] == "ruim.com"
    assert opcoes["dados"]["tipo"] == "trancado" and opcoes["dados"]["quarentena"]


def test_cli_recusa_avisa(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["guarnicao", "quarentena", "trancar", str(tmp_path / "x"),
                                      "--sha256", "0" * 64])
    assert cli.main() == 2
    assert avisos[0][0][0] == "Não deu para trancar"
