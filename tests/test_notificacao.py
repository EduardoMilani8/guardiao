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
    # "low" não: o GNOME não mostra balão de urgência baixa, e passageiro não fica na lista.
    assert cmd[cmd.index("--urgency") + 1] == "normal"
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


def test_dados_viram_hints_de_texto():
    cmd = notificacao.comando("Ameaça encontrada", "x.exe\nEICAR", urgente=True,
                              dados={"tipo": "ameaca", "arquivo": "$(rm -rf ~).pdf", "sha256": ""})
    assert "--hint=string:x-guarnicao-tipo:ameaca" in cmd
    assert "--hint=string:x-guarnicao-arquivo:$(rm -rf ~).pdf" in cmd   # um argumento só, sem shell
    assert not any("x-guarnicao-sha256" in a for a in cmd)              # vazio não vai
    assert cmd[-2:] == ["Ameaça encontrada", "x.exe\nEICAR"]


def test_chave_desconhecida_e_recusada():
    import pytest
    with pytest.raises(ValueError):
        notificacao.comando("t", "c", dados={"comando": "rm"})


def test_personagem_pela_camada():
    assert notificacao.personagem("hash") == "cavaleiro"
    assert notificacao.personagem("clamav") == "cavaleiro"
    assert notificacao.personagem("yara") == "arqueira"
    assert notificacao.personagem("heuristica") == "vidente"
    assert notificacao.personagem(None) == "cavaleiro"


def test_dados_de_um_resultado():
    from pathlib import Path
    from guarnicao.scanner import Resultado
    r = Resultado(caminho=Path("/home/x/Downloads/fatura.pdf.exe"), sha256="ab" * 32,
                  ameaca="EICAR", camada="yara")   # infectado é propriedade: vem de `ameaca`
    d = notificacao.dados_de(r, "ameaca")
    assert d == {"tipo": "ameaca", "personagem": "arqueira", "arquivo": "fatura.pdf.exe",
                 "caminho": "/home/x/Downloads/fatura.pdf.exe", "sha256": "ab" * 32, "quarentena": ""}
    assert notificacao.dados_de(r, "trancado", "id1")["personagem"] == "carcereiro"


def test_aviso_de_bases_uma_vez_por_dia(tmp_path, monkeypatch):
    from datetime import datetime
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    marca = tmp_path / "ultimo-aviso-bases"
    dia = datetime(2026, 11, 8, 9, 0)
    assert not notificacao.aviso_bases([], False, dia, marca)              # tudo em dia: silêncio
    assert notificacao.aviso_bases(["yara-forge: sem atualizar há 9 dia(s)"], False, dia, marca)
    assert not notificacao.aviso_bases(["yara-forge: sem atualizar há 9 dia(s)"], False, dia, marca)
    assert notificacao.aviso_bases([], True, datetime(2026, 11, 9, 9, 0), marca)
    (titulo, corpo), opcoes = avisos[0]
    assert titulo == "Suas bases estão desatualizadas" and "yara-forge" in corpo
    assert opcoes["dados"] == {"tipo": "bases", "personagem": "cavaleiro"}
    assert "freshclam" in avisos[1][0][1]


def test_nome_com_traco_nao_vira_opcao(tmp_path):
    # Um malware chamado "-fatura.pdf.exe" não pode silenciar o aviso: sem "--",
    # o notify-send lê o corpo como opção desconhecida e sai sem mostrar nada.
    import shutil
    import subprocess
    cmd = notificacao.comando("-Ameaça", "-fatura.pdf.exe\nEICAR", dados={"arquivo": "-fatura.pdf.exe"})
    assert cmd[-3:] == ["--", "-Ameaça", "-fatura.pdf.exe\nEICAR"]
    if shutil.which("notify-send"):
        # Barramento que não existe: só queremos ver como ele lê os argumentos.
        env = {"PATH": os.environ["PATH"], "DBUS_SESSION_BUS_ADDRESS": f"unix:path={tmp_path}/nada"}
        saida = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=10)
        assert "Unknown option" not in saida.stderr
