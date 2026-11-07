import json
import sys
from datetime import datetime

from guarnicao import __main__ as cli
from guarnicao import historico, notificacao, quarentena, varredura
from guarnicao.scanner import Resultado

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def registro(tipo="rápida", ameacas=0, quando="2026-11-04T03:00:00"):
    resumo = varredura.Resumo(analisados=10, em_cache=90, ameacas=ameacas, segundos=12.34)
    return historico.novo(tipo, "agendada", datetime.fromisoformat(quando), resumo, [])


def test_registra_e_lista_do_mais_recente(tmp_path):
    arquivo = tmp_path / "h.jsonl"
    historico.registrar(registro("rápida", quando="2026-11-01T03:00:00"), arquivo)
    historico.registrar(registro("completa", ameacas=1, quando="2026-11-02T03:00:00"), arquivo)
    historico.registrar(registro("rápida", quando="2026-11-03T03:00:00"), arquivo)
    [r3, r2, r1] = historico.listar(arquivo=arquivo)
    assert (r3.inicio, r2.tipo, r2.ameacas, r1.total, r1.segundos) == ("2026-11-03T03:00:00", "completa", 1, 100, 12.3)
    assert historico.ultima("completa", arquivo).quando == datetime(2026, 11, 2, 3)
    assert historico.ultima("pasta", arquivo) is None
    assert len(historico.listar(2, arquivo)) == 2


def test_linha_estragada_nao_derruba_o_resto(tmp_path):
    arquivo = tmp_path / "h.jsonl"
    historico.registrar(registro(), arquivo)
    with arquivo.open("a") as f:
        f.write('{"metade de uma linha\n{"campo_que_nao_existe": 1}\n')
    historico.registrar(registro("completa"), arquivo)
    assert [r.tipo for r in historico.listar(arquivo=arquivo)] == ["completa", "rápida"]


def test_mantem_so_os_mais_recentes(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "MAX_REGISTROS", 3)
    arquivo = tmp_path / "h.jsonl"
    for dia in range(1, 6):
        historico.registrar(registro(quando=f"2026-11-0{dia}T03:00:00"), arquivo)
    assert [r.quando.day for r in historico.listar(arquivo=arquivo)] == [5, 4, 3]


def test_ameacas_vem_antes_quando_corta(monkeypatch):
    monkeypatch.setattr(historico, "MAX_ACHADOS", 2)
    achados = [historico.achado(Resultado(f"/s{i}", "0" * 64, pontuacao=60)) for i in range(3)]
    achados.append(historico.achado(Resultado("/ruim", "1" * 64, ameaca="X"), quarentena="abc"))
    r = historico.novo("rápida", "terminal", datetime.now(), varredura.Resumo(), achados)
    assert r.achados[0] == {**r.achados[0], "caminho": "/ruim", "veredito": "ameaca", "quarentena": "abc"}
    assert len(r.achados) == 2


def rodar(monkeypatch, *argumentos):
    monkeypatch.setattr(sys, "argv", ["guarnicao", *argumentos])
    return cli.main()


def test_varrer_grava_no_historico_com_o_id_da_quarentena(tmp_path, monkeypatch, capsys):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "teste.com").write_bytes(EICAR)
    (pasta / "notas.txt").write_text("nada aqui")
    assert rodar(monkeypatch, "varrer", str(pasta), "--isolar", "--processos", "1") == 1
    [r] = historico.listar()
    assert (r.origem, r.tipo, r.ameacas, r.total) == ("terminal", str(pasta), 1, 2)
    [a] = r.achados
    assert a["ameaca"] == "EICAR-Test-File" and a["quarentena"] in {e["id"] for e in quarentena.listar()}
    capsys.readouterr()
    assert rodar(monkeypatch, "historico", "--achados") == 0
    saida = capsys.readouterr().out
    assert "1 ameaça(s)" in saida and "na quarentena" in saida


def test_agendada_avisa_e_nao_falha(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "teste.com").write_bytes(EICAR)
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    assert rodar(monkeypatch, "varrer", str(pasta), "--agendada", "--processos", "1") == 0
    [((titulo, corpo), opcoes)] = avisos
    assert "1 ameaça(s)" in titulo and "launcher" in corpo and opcoes["urgente"]
    assert historico.listar()[0].origem == "agendada"
    assert (pasta / "teste.com").exists()        # agendada não isola sozinha


def test_historico_vazio(monkeypatch, capsys):
    assert rodar(monkeypatch, "historico") == 0
    assert "Nenhuma varredura" in capsys.readouterr().out


def test_arquivo_e_json_por_linha(tmp_path):
    arquivo = tmp_path / "h.jsonl"
    historico.registrar(registro(), arquivo)
    assert json.loads(arquivo.read_text())["origem"] == "agendada"
