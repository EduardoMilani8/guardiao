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


def test_discreto_e_passageiro():
    cmd = notificacao.comando("Varredura rápida concluída ✓", "305 arquivos", discreto=True)
    assert cmd[cmd.index("--urgency") + 1] == "low"
    assert "--transient" in cmd          # não fica guardado na lista do GNOME
    assert cmd[cmd.index("--expire-time") + 1] == "6000"


def test_texto_do_resumo_limpo():
    from datetime import datetime
    titulo, corpo = notificacao.texto_resumo_limpo("rápida", 4210, datetime(2026, 11, 8, 12, 51))
    assert titulo == "Varredura rápida concluída ✓"
    assert corpo == "4.210 arquivos, tudo limpo · hoje, 12:51"


def test_resumo_limpo_no_maximo_um_por_dia(tmp_path, monkeypatch):
    from datetime import datetime
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    marca = tmp_path / "ultimo-resumo"
    assert notificacao.resumo_limpo("rápida", 305, datetime(2026, 11, 8, 12, 51), marca)
    assert not notificacao.resumo_limpo("completa", 411932, datetime(2026, 11, 8, 13, 30), marca)
    assert notificacao.resumo_limpo("rápida", 305, datetime(2026, 11, 9, 12, 51), marca)
    assert len(avisos) == 2 and all(k["discreto"] for _, k in avisos)
