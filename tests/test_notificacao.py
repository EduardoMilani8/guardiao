import os

from guarnicao import notificacao


def test_sessoes_so_de_usuarios_com_barramento(tmp_path):
    for uid, com_barramento in ((0, True), (os.getuid(), True), (os.getuid() + 1, False)):
        (tmp_path / str(uid)).mkdir()
        if com_barramento:
            (tmp_path / str(uid) / "bus").touch()
    sessoes = notificacao._sessoes(tmp_path)
    if os.getuid() >= 1000:
        assert [(uid, bus.parent.name) for uid, _, bus in sessoes] == [(os.getuid(), str(os.getuid()))]
    else:
        assert sessoes == []


def test_texto_nunca_vira_comando():
    titulo, corpo = "Ameaça", "$(rm -rf ~).pdf"
    assert notificacao.comando(titulo, corpo)[-2:] == [titulo, corpo]
