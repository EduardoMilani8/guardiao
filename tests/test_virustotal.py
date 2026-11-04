import io
import json
import urllib.error
from pathlib import Path

import pytest

from guardiao import __main__ as cli
from guardiao import heuristicas, scanner, virustotal
from guardiao.virustotal import Laudo, SemCota

SHA = "a" * 64


def resultado(**campos) -> scanner.Resultado:
    return scanner.Resultado(caminho=Path("/tmp/x"), sha256=SHA, **campos)


class Contador:
    """Faz o papel do VirusTotal e conta quantas vezes foi chamado."""

    def __init__(self, laudo=Laudo(0, 0)):
        self.laudo, self.chamadas = laudo, 0

    def __call__(self, sha, chave):
        self.chamadas += 1
        return self.laudo


def test_resposta_guardada_nao_consulta_de_novo():
    pedir = Contador(Laudo(3, 70, "trojan.x"))
    assert virustotal.consultar(SHA, "k", agora=1000, pedir=pedir) == Laudo(3, 70, "trojan.x")
    assert virustotal.consultar(SHA, "k", agora=1000 + 86400, pedir=pedir) == Laudo(3, 70, "trojan.x")
    assert pedir.chamadas == 1


def test_conhecido_vence_em_uma_semana_e_desconhecido_em_um_dia():
    conhecido, desconhecido = Contador(Laudo(0, 70)), Contador(Laudo(0, 0))
    virustotal.consultar(SHA, "k", agora=0, pedir=conhecido)
    virustotal.consultar(SHA, "k", agora=virustotal.VALIDADE_CONHECIDO + 1, pedir=conhecido)
    assert conhecido.chamadas == 2

    outro = "b" * 64
    virustotal.consultar(outro, "k", agora=0, pedir=desconhecido)
    virustotal.consultar(outro, "k", agora=virustotal.VALIDADE_DESCONHECIDO - 1, pedir=desconhecido)
    virustotal.consultar(outro, "k", agora=virustotal.VALIDADE_DESCONHECIDO + 1, pedir=desconhecido)
    assert desconhecido.chamadas == 2


def test_limite_por_minuto_diz_quanto_esperar():
    pedir = Contador()
    for i in range(virustotal.POR_MINUTO):
        virustotal.consultar(f"{i:064x}", "k", agora=100 + i, pedir=pedir)
    with pytest.raises(SemCota) as erro:
        virustotal.consultar("f" * 64, "k", agora=110, pedir=pedir)
    assert erro.value.espera == pytest.approx(50)
    # Passado o minuto, abre vaga.
    virustotal.consultar("f" * 64, "k", agora=161, pedir=pedir)


def test_limite_do_dia_nao_tem_espera(monkeypatch):
    monkeypatch.setattr(virustotal, "POR_DIA", 3)
    pedir = Contador()
    for i in range(3):
        virustotal.consultar(f"{i:064x}", "k", agora=i * 100, pedir=pedir)
    with pytest.raises(SemCota) as erro:
        virustotal.consultar("f" * 64, "k", agora=1000, pedir=pedir)
    assert erro.value.espera is None
    virustotal.consultar("f" * 64, "k", agora=86400 + 1, pedir=pedir)   # no dia seguinte, volta


def test_ameaca_com_cinco_antivirus():
    r = virustotal.aplicar(resultado(), Laudo(5, 70, "trojan.mirai"))
    assert r.infectado and r.camada == "virustotal"
    assert "trojan.mirai" in r.ameaca and "5 de 70" in r.ameaca


def test_dois_a_quatro_viram_suspeito_e_um_so_vira_motivo():
    r = virustotal.aplicar(resultado(), Laudo(2, 70))
    assert r.suspeito and r.pontuacao == heuristicas.LIMIAR_SUSPEITO
    r = virustotal.aplicar(resultado(), Laudo(1, 70))
    assert not r.suspeito and r.motivos


def test_nunca_rebaixa_e_ignora_desconhecido():
    r = virustotal.aplicar(resultado(ameaca="EICAR"), Laudo(0, 70))
    assert r.ameaca == "EICAR"
    r = virustotal.aplicar(resultado(pontuacao=60), Laudo(0, 0))
    assert r.suspeito and not r.motivos


def resposta_http(codigo, corpo=b"{}"):
    def urlopen(pedido, timeout):
        assert pedido.get_header("X-apikey") == "k"
        if codigo != 200:
            raise urllib.error.HTTPError(pedido.full_url, codigo, "", {}, io.BytesIO(b""))
        return io.BytesIO(corpo)
    return urlopen


def test_le_a_resposta_da_api(monkeypatch):
    corpo = json.dumps({"data": {"attributes": {
        "last_analysis_stats": {"malicious": 40, "suspicious": 2, "undetected": 20, "harmless": 0},
        "popular_threat_classification": {"suggested_threat_label": "trojan.gafgyt"}}}}).encode()
    monkeypatch.setattr(virustotal.urllib.request, "urlopen", resposta_http(200, corpo))
    assert virustotal._pedir(SHA, "k") == Laudo(40, 62, "trojan.gafgyt")


def test_404_e_desconhecido_e_429_e_sem_cota(monkeypatch):
    monkeypatch.setattr(virustotal.urllib.request, "urlopen", resposta_http(404))
    assert virustotal._pedir(SHA, "k") == Laudo(0, 0)
    monkeypatch.setattr(virustotal.urllib.request, "urlopen", resposta_http(429))
    with pytest.raises(SemCota):
        virustotal._pedir(SHA, "k")


def test_sem_chave_nao_consulta(monkeypatch):
    monkeypatch.setattr(virustotal, "consultar", lambda *a, **k: pytest.fail("consultou sem chave"))
    consulta = cli.ConsultaVirusTotal()
    assert consulta.chave is None
    assert not consulta(resultado(pontuacao=60)).infectado


def test_varredura_para_no_maximo(monkeypatch, capsys):
    monkeypatch.setenv("GUARDIAO_VIRUSTOTAL_CHAVE", "k")
    feitas = []
    monkeypatch.setattr(virustotal, "consultar", lambda sha, chave: feitas.append(sha) or Laudo(9, 70))
    consulta = cli.ConsultaVirusTotal(maximo=2)
    resultados = [consulta(resultado(pontuacao=60)) for _ in range(4)]
    assert len(feitas) == 2
    assert [r.infectado for r in resultados] == [True, True, False, False]
    assert "o resto fica para a próxima" in capsys.readouterr().out


def test_cota_do_dia_esgotada_avisa_uma_vez(monkeypatch, capsys):
    monkeypatch.setenv("GUARDIAO_VIRUSTOTAL_CHAVE", "k")

    def sem_cota(sha, chave):
        raise SemCota("limite de 500 consultas por dia")
    monkeypatch.setattr(virustotal, "consultar", sem_cota)
    consulta = cli.ConsultaVirusTotal()
    consulta(resultado(pontuacao=60))
    consulta(resultado(pontuacao=60))
    assert capsys.readouterr().out.count("500 consultas") == 1


def test_varredura_conta_o_suspeito_que_virou_ameaca(monkeypatch, tmp_path):
    from guardiao import historico, varredura
    monkeypatch.setenv("GUARDIAO_VIRUSTOTAL_CHAVE", "k")
    monkeypatch.setattr(virustotal, "consultar", lambda sha, chave: Laudo(30, 70, "trojan.x"))
    suspeito = scanner.Resultado(caminho=tmp_path / "x", sha256=SHA, pontuacao=60, motivos=["algo"])
    monkeypatch.setattr(varredura, "executar", lambda *a, **k: iter([suspeito, varredura.Resumo(analisados=1, suspeitos=1)]))
    monkeypatch.setattr("sys.argv", ["guardiao", "varrer", str(tmp_path)])
    assert cli.main() == 1
    [registro] = historico.listar()
    assert (registro.ameacas, registro.suspeitos) == (1, 0)
    assert registro.achados[0]["veredito"] == "ameaca"
