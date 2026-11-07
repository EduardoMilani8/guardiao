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
    assert "1 ameaça(s)" in titulo and opcoes["urgente"]
    assert opcoes["dados"]["tipo"] == "ameaca" and opcoes["dados"]["arquivo"] == "teste.com"
    assert corpo.splitlines()[0] == "teste.com"
    assert historico.listar()[0].origem == "agendada"
    assert (pasta / "teste.com").exists()        # agendada não isola sozinha


def test_historico_vazio(monkeypatch, capsys):
    assert rodar(monkeypatch, "historico") == 0
    assert "Nenhuma varredura" in capsys.readouterr().out


def test_arquivo_e_json_por_linha(tmp_path):
    arquivo = tmp_path / "h.jsonl"
    historico.registrar(registro(), arquivo)
    assert json.loads(arquivo.read_text())["origem"] == "agendada"


def test_agendada_limpa_manda_resumo_discreto(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "notas.txt").write_text("nada aqui")
    resumos = []
    monkeypatch.setattr(notificacao, "resumo_limpo", lambda *a: resumos.append(a))
    assert rodar(monkeypatch, "varrer", str(pasta), "--agendada", "--processos", "1") == 0
    [(nome, total, _quando)] = resumos
    assert total == 1


def test_manual_limpa_nao_manda_resumo(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "notas.txt").write_text("nada aqui")
    resumos = []
    monkeypatch.setattr(notificacao, "resumo_limpo", lambda *a: resumos.append(a))
    assert rodar(monkeypatch, "varrer", str(pasta), "--processos", "1") == 0
    assert resumos == []


def test_agendada_com_varios_achados_e_um_aviso_so(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "a.com").write_bytes(EICAR)
    (pasta / "b.com").write_bytes(EICAR)
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    rodar(monkeypatch, "varrer", str(pasta), "--agendada", "--processos", "1")
    [((titulo, corpo), opcoes)] = avisos
    assert opcoes["dados"] == {"tipo": "varias"}
    # Igual ao avisos-v3: "2 arquivos perigosos" / "1 ameaça · 1 suspeito · varredura ... de hoje, HH:MM"
    assert titulo == "2 arquivos perigosos"
    assert corpo.startswith("2 ameaças · varredura ") and " de hoje, " in corpo


def test_agendada_com_isolar_avisa_trancado_e_nao_oferece_trancar(tmp_path, monkeypatch):
    pasta = tmp_path / "baixados"
    pasta.mkdir()
    (pasta / "teste.com").write_bytes(EICAR)
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    assert rodar(monkeypatch, "varrer", str(pasta), "--agendada", "--isolar", "--processos", "1") == 0
    [((titulo, corpo), opcoes)] = avisos
    dados = opcoes["dados"]
    assert dados["tipo"] == "trancado" and dados["quarentena"]
    assert not dados.get("sha256")              # já está trancado: botão é Desfazer
    assert not opcoes["urgente"]                # trancado some sozinho (spec)


def test_monitor_trancado_some_sozinho(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    item = Resultado(caminho=tmp_path / "x.exe", sha256="ab" * 32, ameaca="EICAR", camada="hash")
    cli.avisar_do_monitor(item, "id-da-cela")
    [((titulo, _), opcoes)] = avisos
    assert titulo == "Trancado na quarentena" and not opcoes.get("urgente")
    assert opcoes["dados"]["quarentena"] == "id-da-cela"
    avisos.clear()
    cli.avisar_do_monitor(item, None)
    assert avisos[0][0][0] == "Ameaça encontrada" and avisos[0][1]["urgente"]


def test_monitor_suspeito_diz_algo_suspeito(tmp_path, monkeypatch):
    avisos = []
    monkeypatch.setattr(notificacao, "notificar", lambda *a, **k: avisos.append((a, k)))
    item = Resultado(caminho=tmp_path / "x.sh", sha256="ab" * 32, pontuacao=60, motivos=["baixa script"])
    assert item.suspeito
    cli.avisar_do_monitor(item, None)
    assert avisos[0][0] == ("Algo suspeito", "x.sh\nbaixa script")


def test_contagem_dos_achados():
    assert notificacao.contar_achados(2, 0) == "2 ameaças"
    assert notificacao.contar_achados(1, 1) == "1 ameaça · 1 suspeito"
    assert notificacao.contar_achados(0, 3) == "3 suspeitos"
