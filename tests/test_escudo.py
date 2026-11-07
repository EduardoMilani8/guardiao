from datetime import datetime

from guarnicao import escudo, historico, varredura

AGORA = datetime(2026, 11, 8, 12, 40)


def servicos(protetor=True, monitor=True, avisos=(), freshclam=False):
    return {"protetor": {"instalado": True, "ativo": protetor, "ligar": "sudo systemctl enable --now guarnicao-protetor"},
            "monitor": {"instalado": True, "ativo": monitor, "ligar": "systemctl --user enable --now guarnicao-monitor"},
            "bases": {"conferidas": AGORA.timestamp() - 180, "avisos": list(avisos), "freshclam_parado": freshclam}}


def registro(achados=(), total=305, quando="2026-11-08T12:30:00"):
    resumo = varredura.Resumo(analisados=total, ameacas=sum(a["veredito"] == "ameaca" for a in achados))
    return historico.novo("rápida", "agendada", datetime.fromisoformat(quando), resumo, list(achados))


def test_tudo_certo():
    e = escudo.montar(servicos(), [registro()], None, AGORA)
    assert e["estado"] == "certo" and e["titulo"] == "Você está protegido"
    assert e["linhas"][:2] == ["Última: rápida · hoje, 12:30", "✓ 305 arquivos, tudo limpo"]
    assert e["linhas"][2] == "Bases atualizadas há 3 min"
    assert e["acoes"] == ["varrer", "abrir"]


def test_procurando_enche_em_passos():
    e = escudo.montar(servicos(), [registro()], {"feitos": 183, "total": 305, "pode_parar": True}, AGORA)
    assert e["estado"] == "procurando" and e["nivel"] == 3
    assert e["linhas"][0] == "183 de 305 arquivos · 60%"
    assert e["pct"] == 60          # a barrinha dourada do menu (barra-v2)
    assert e["acoes"] == ["abrir", "parar"]


def test_procurando_no_launcher_nao_oferece_parar():
    e = escudo.montar(servicos(), [], {"feitos": 0, "total": 10, "pode_parar": False}, AGORA)
    assert e["nivel"] == 1 and e["acoes"] == ["abrir"]


def test_atencao_bases_velhas():
    e = escudo.montar(servicos(avisos=["yara-forge: sem atualizar há 9 dia(s)"]), [registro()], None, AGORA)
    assert e["estado"] == "atencao" and e["titulo"] == "Suas bases estão desatualizadas"
    assert e["acoes"] == ["atualizar", "abrir"]


def test_atencao_protetor_parado():
    e = escudo.montar(servicos(protetor=False), [registro()], None, AGORA)
    assert e["estado"] == "atencao" and "protetor" in e["titulo"].lower()


def test_ameaca_vence_tudo(tmp_path):
    arq = tmp_path / "ruim.exe"
    arq.write_text("x")
    achado = {"caminho": str(arq), "veredito": "ameaca", "ameaca": "EICAR", "camada": "hash",
              "sha256": "a" * 64, "quarentena": None}
    e = escudo.montar(servicos(protetor=False, avisos=["x"]), [registro([achado])],
                      {"feitos": 1, "total": 9, "pode_parar": True}, AGORA)
    assert e["estado"] == "ameaca" and e["titulo"] == "1 arquivo perigoso"
    assert e["linhas"][0] == "1 ameaça"     # como no barra-v2: "1 ameaça · 1 suspeito"
    assert e["acoes"][0] == "trancar"


def test_sem_varredura_ainda():
    e = escudo.montar(servicos(), [], None, AGORA)
    assert e["estado"] == "certo" and "Nenhuma varredura ainda" in e["linhas"]
