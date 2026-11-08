from datetime import datetime, timedelta

from guarnicao import historico, semanal, varredura

AGORA = datetime(2026, 11, 8, 14, 0)
QUINZE_MIN = 15 * 60 * 1000


def completa(quando: datetime, tipo="completa"):
    return historico.novo(tipo, "agendada", quando, varredura.Resumo(analisados=10), [])


def test_devida_sem_completa_na_semana():
    assert semanal.devida([], AGORA)
    assert semanal.devida([completa(AGORA - timedelta(days=8))], AGORA)
    assert not semanal.devida([completa(AGORA - timedelta(days=2))], AGORA)
    # Rápidas não contam.
    assert semanal.devida([completa(AGORA - timedelta(hours=1), "rápida")], AGORA)


def test_pc_parado_e_na_tomada_comeca_sozinha():
    assert semanal.decidir(devida=True, ocioso_ms=QUINZE_MIN, na_tomada=True, perguntou_hoje=True) == "rodar"


def test_pc_em_uso_pergunta_uma_vez_por_dia():
    assert semanal.decidir(devida=True, ocioso_ms=1000, na_tomada=True, perguntou_hoje=False) == "perguntar"
    assert semanal.decidir(devida=True, ocioso_ms=1000, na_tomada=True, perguntou_hoje=True) == "nada"


def test_na_bateria_nunca_comeca_sozinha():
    assert semanal.decidir(devida=True, ocioso_ms=QUINZE_MIN * 4, na_tomada=False, perguntou_hoje=False) == "perguntar"


def test_sem_saber_se_esta_parado_so_pergunta():
    # Fora do GNOME não dá para saber há quanto tempo o PC está parado.
    assert semanal.decidir(devida=True, ocioso_ms=None, na_tomada=True, perguntou_hoje=False) == "perguntar"


def test_ja_feita_nada():
    assert semanal.decidir(devida=False, ocioso_ms=QUINZE_MIN, na_tomada=True, perguntou_hoje=False) == "nada"


def test_na_tomada(tmp_path):
    def fonte(nome, tipo, online=None):
        d = tmp_path / nome
        d.mkdir()
        (d / "type").write_text(tipo + "\n")
        if online is not None:
            (d / "online").write_text(f"{online}\n")
    assert semanal.na_tomada(tmp_path)                 # sem bateria (desktop): sempre na tomada
    fonte("BAT0", "Battery")
    fonte("AC", "Mains", 0)
    assert not semanal.na_tomada(tmp_path)
    (tmp_path / "AC" / "online").write_text("1\n")
    assert semanal.na_tomada(tmp_path)


def test_ocioso_le_o_gnome(monkeypatch):
    import subprocess
    saida = subprocess.CompletedProcess([], 0, stdout="(uint64 1234567,)\n", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: saida)
    assert semanal.ocioso_ms() == 1234567
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert semanal.ocioso_ms() is None


def rodar_cli(monkeypatch, *args):
    import sys

    from guarnicao import __main__ as cli
    monkeypatch.setattr(sys, "argv", ["guarnicao", *args])
    return cli.main()


def preparar(monkeypatch, tmp_path, ocioso):
    from guarnicao import andamento, notificacao
    avisos, iniciadas = [], []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr(semanal, "MARCA", tmp_path / "perguntou")
    monkeypatch.setattr(semanal, "ocioso_ms", lambda: ocioso)
    monkeypatch.setattr(semanal, "na_tomada", lambda: True)
    monkeypatch.setattr(semanal, "iniciar", lambda: iniciadas.append(1))
    monkeypatch.setattr(andamento, "ler", lambda *a, **k: None)
    return avisos, iniciadas


def test_cli_pergunta_uma_vez_e_oferece_varrer_agora(monkeypatch, tmp_path):
    avisos, iniciadas = preparar(monkeypatch, tmp_path, ocioso=1000)
    assert rodar_cli(monkeypatch, "semanal") == 0
    assert rodar_cli(monkeypatch, "semanal") == 0
    [((titulo, _), opcoes)] = avisos
    assert titulo == "Hora da varredura completa da semana"
    assert opcoes["dados"]["tipo"] == "semanal" and not iniciadas


def test_cli_pc_parado_comeca_sem_perguntar(monkeypatch, tmp_path):
    avisos, iniciadas = preparar(monkeypatch, tmp_path, ocioso=semanal.PARADO_MS)
    assert rodar_cli(monkeypatch, "semanal") == 0
    assert iniciadas == [1] and not avisos


def test_cli_agora_e_o_botao(monkeypatch, tmp_path):
    avisos, iniciadas = preparar(monkeypatch, tmp_path, ocioso=0)
    assert rodar_cli(monkeypatch, "semanal", "--agora") == 0
    assert iniciadas == [1]


def test_cli_nada_com_a_completa_rodando(monkeypatch, tmp_path):
    from guarnicao import andamento
    avisos, iniciadas = preparar(monkeypatch, tmp_path, ocioso=semanal.PARADO_MS)
    monkeypatch.setattr(andamento, "ler", lambda *a, **k: {"tipo": "completa", "feitos": 1, "total": 9})
    assert rodar_cli(monkeypatch, "semanal") == 0
    assert not iniciadas and not avisos
