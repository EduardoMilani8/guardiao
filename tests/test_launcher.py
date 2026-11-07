import json
import threading
import urllib.error
import urllib.request

import pytest

from guardiao import assinaturas, eventos, regras_yara, scanner
from guardiao.launcher import servidor

from . import amostras as demo


@pytest.fixture(scope="module")
def url():
    srv = servidor.criar_servidor(0)   # porta 0: o sistema escolhe uma livre
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def ler_eventos(url):
    with urllib.request.urlopen(url, timeout=60) as resposta:
        assert resposta.headers["Content-Type"].startswith("text/event-stream")
        corpo = resposta.read().decode()
    return [json.loads(l.removeprefix("data: ")) for l in corpo.splitlines() if l.startswith("data: ")]


def test_camada_e_veredito_das_amostras(tmp_path):
    pasta = demo.criar_amostras(tmp_path)
    banco, yara = assinaturas.carregar(), regras_yara.carregar()
    por_nome = {e["nome"]: e for e in (eventos.de_resultado(r, pasta) for r in scanner.varrer(pasta, banco, yara))}

    assert (por_nome["jogo-gratis-crackeado.com"]["veredito"], por_nome["jogo-gratis-crackeado.com"]["camada"]) == ("ameaca", "hash")
    assert (por_nome["fotos-da-praia.jpg"]["veredito"], por_nome["fotos-da-praia.jpg"]["camada"]) == ("suspeito", "heuristica")
    assert por_nome["notas-da-aula.txt"] == {**por_nome["notas-da-aula.txt"], "veredito": "limpo", "camada": None}
    if yara:
        assert (por_nome["atualizar-drivers.sh"]["veredito"], por_nome["atualizar-drivers.sh"]["camada"]) == ("ameaca", "yara")
        assert (por_nome["instalar-tema.sh"]["veredito"], por_nome["instalar-tema.sh"]["camada"]) == ("suspeito", "yara")


def escolher(url, tipo="application/json"):
    pedido = urllib.request.Request(f"{url}/api/escolher-pasta", data=b"{}", method="POST",
                                    headers={"Content-Type": tipo})
    with urllib.request.urlopen(pedido, timeout=5) as r:
        return json.loads(r.read())


def test_pasta_escolhida_e_varrida(url, tmp_path, monkeypatch):
    pasta = demo.criar_amostras(tmp_path)
    monkeypatch.setattr(servidor, "escolher_pasta", lambda: pasta)
    resposta = escolher(url)
    assert "id" in resposta and str(pasta) not in json.dumps(resposta)   # a página só vê um id
    evs = ler_eventos(f"{url}/api/varrer?alvo=pasta&id={resposta['id']}")
    assert evs[0]["tipo"] == "inicio" and evs[-1]["tipo"] == "fim"
    assert evs[-1]["ameaca"] >= 1 and evs[-1]["suspeito"] >= 1
    # Arquivos limpos não geram evento próprio: só achados, e o progresso em lotes.
    achados = [e for e in evs if e["tipo"] == "arquivo"]
    assert len(achados) == evs[-1]["ameaca"] + evs[-1]["suspeito"]
    assert all(e["veredito"] != "limpo" for e in achados)
    assert any(e["tipo"] == "progresso" for e in evs)


def test_seletor_cancelado(url, monkeypatch):
    monkeypatch.setattr(servidor, "escolher_pasta", lambda: None)
    assert escolher(url) == {"cancelado": True}


def test_seletor_so_aceita_json(url, monkeypatch):
    # Um <form> de outro site só manda tipos "simples" como este.
    monkeypatch.setattr(servidor, "escolher_pasta", lambda: pytest.fail("não devia abrir o seletor"))
    with pytest.raises(urllib.error.HTTPError) as erro:
        escolher(url, "application/x-www-form-urlencoded")
    assert erro.value.code == 415


def test_recusa_host_de_fora(url):
    # DNS rebinding: o domínio do atacante apontando para 127.0.0.1.
    pedido = urllib.request.Request(f"{url}/api/varrer?alvo=rapida", headers={"Host": "malicioso.com:80"})
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(pedido, timeout=5)
    assert erro.value.code == 403


def test_pagina_e_estaticos(url):
    with urllib.request.urlopen(f"{url}/", timeout=5) as r:
        assert b"Guardi" in r.read()
    for nome in servidor.ESTATICOS:
        with urllib.request.urlopen(f"{url}/estatico/{nome}", timeout=5) as r:
            assert r.status == 200


@pytest.mark.parametrize("caminho", [
    "/api/varrer?alvo=/etc",                # alvo só por nome, nunca caminho
    "/api/varrer",
    "/api/varrer?alvo=pasta&id=inventado",  # só pastas escolhidas no seletor
    "/api/outra-coisa",
    "/estatico/../servidor.py",             # nada fora da lista de estáticos
    "/estatico/demo.py",
    "/api/varrer?alvo=demo",                # a demonstração saiu
])
def test_recusa_pedidos_fora_do_permitido(url, caminho):
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(f"{url}{caminho}", timeout=5)
    assert erro.value.code in (400, 404)


def test_escuta_so_localmente():
    srv = servidor.criar_servidor(0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def pedir_isolar(url, id_, tipo="application/json", host=None):
    cabecalhos = {"Content-Type": tipo, **({"Host": host} if host else {})}
    pedido = urllib.request.Request(f"{url}/api/isolar", data=json.dumps({"id": id_}).encode(),
                                    method="POST", headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as erro:
        corpo = erro.read()
        return erro.code, json.loads(corpo) if corpo.startswith(b"{") else {}


def varrer_pasta(url, pasta, monkeypatch):
    monkeypatch.setattr(servidor, "escolher_pasta", lambda: pasta)
    return ler_eventos(f"{url}/api/varrer?alvo=pasta&id={escolher(url)['id']}")


def test_carcereiro_tranca_com_um_clique(url, tmp_path, monkeypatch):
    from guardiao import historico, quarentena
    pasta = demo.criar_amostras(tmp_path)
    evs = varrer_pasta(url, pasta, monkeypatch)
    ameacas = [e for e in evs if e["tipo"] == "arquivo" and e["veredito"] == "ameaca"]
    assert ameacas and all(e["isolar"] for e in ameacas)
    assert all(e["isolar"] for e in evs if e.get("veredito") == "suspeito")   # suspeito também se tranca
    alvo = ameacas[0]
    assert str(pasta) not in alvo["isolar"]                       # um código, não um caminho

    status, resposta = pedir_isolar(url, alvo["isolar"])
    assert status == 200 and not (pasta / alvo["caminho"]).exists()
    assert resposta["quarentena"] in {e["id"] for e in quarentena.listar()}
    # O histórico da varredura feita pelo launcher anota a cela.
    [r] = historico.listar()
    assert r.origem == "launcher"
    assert [a["quarentena"] for a in r.achados if a["caminho"] == str(pasta / alvo["caminho"])] == [resposta["quarentena"]]
    assert pedir_isolar(url, alvo["isolar"])[0] == 404             # o código vale uma vez


def test_carcereiro_nao_tranca_arquivo_que_mudou(url, tmp_path, monkeypatch):
    pasta = demo.criar_amostras(tmp_path)
    alvo = next(e for e in varrer_pasta(url, pasta, monkeypatch) if e.get("veredito") == "ameaca")
    (pasta / alvo["caminho"]).write_text("trocado depois da varredura")
    status, resposta = pedir_isolar(url, alvo["isolar"])
    assert status == 409 and "mudou" in resposta["erro"]
    assert (pasta / alvo["caminho"]).exists()


@pytest.mark.parametrize("id_, tipo, host, esperado", [
    ("inventado", "application/json", None, 404),
    ("qualquer", "text/plain", None, 415),                      # <form> de outro site
    ("qualquer", "application/json", "malicioso.com:80", 403),  # DNS rebinding
])
def test_isolar_recusa(url, id_, tipo, host, esperado):
    assert pedir_isolar(url, id_, tipo, host)[0] == esperado


def test_historico_oferece_o_que_a_agendada_achou(url, tmp_path):
    from datetime import datetime

    from guardiao import historico, varredura
    ruim = tmp_path / "ruim.bin"
    ruim.write_bytes(b"conteudo")
    sumiu = tmp_path / "sumiu.bin"
    achados = [historico.achado(scanner.Resultado(c, scanner.calcular_sha256(ruim) if c == ruim else "0" * 64,
                                                  ameaca="Teste.Ameaca")) for c in (ruim, sumiu)]
    historico.registrar(historico.novo("rápida", "agendada", datetime(2026, 11, 4, 12, 30),
                                       varredura.Resumo(analisados=5, ameacas=2), achados))
    with urllib.request.urlopen(f"{url}/api/historico", timeout=5) as r:
        dados = json.loads(r.read())
    [registro] = dados["registros"]
    assert (registro["inicio"], registro["origem"]) == ("2026-11-04T12:30:00", "agendada")
    assert [a["nome"] for a in registro["achados"]] == ["ruim.bin", "sumiu.bin"]
    [pendente] = dados["pendentes"]                                  # o que sumiu não aparece
    assert pendente["nome"] == "ruim.bin" and pendente["origem"] == "agendada"
    assert pedir_isolar(url, pendente["id"])[0] == 200 and not ruim.exists()
    with urllib.request.urlopen(f"{url}/api/historico", timeout=5) as r:
        assert json.loads(r.read())["pendentes"] == []


def pedir(url, rota, dados=None, tipo="application/json"):
    pedido = urllib.request.Request(f"{url}{rota}", data=json.dumps(dados or {}).encode(),
                                    method="POST", headers={"Content-Type": tipo})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as erro:
        corpo = erro.read()
        return erro.code, json.loads(corpo) if corpo.startswith(b"{") else {}


def ler_json(url, rota):
    with urllib.request.urlopen(f"{url}{rota}", timeout=10) as r:
        return json.loads(r.read())


def test_quarentena_pelo_painel_devolve_e_apaga(url, tmp_path):
    from guardiao import quarentena
    um, dois = tmp_path / "um.bin", tmp_path / "dois.bin"
    um.write_bytes(b"1")
    dois.write_bytes(b"22")
    quarentena.isolar(um, "0" * 64, "Teste.Um", camada="hash")
    quarentena.isolar(dois, "1" * 64, "Teste.Dois", camada="yara", veredito="suspeito")
    itens = {i["nome"]: i for i in ler_json(url, "/api/quarentena")["itens"]}
    assert (itens["dois.bin"]["tamanho"], itens["dois.bin"]["veredito"]) == (2, "suspeito")

    assert pedir(url, "/api/devolver", {"id": itens["um.bin"]["id"]})[0] == 200 and um.exists()
    assert pedir(url, "/api/apagar", {"id": itens["dois.bin"]["id"]})[0] == 200 and not dois.exists()
    restantes = {i["id"] for i in ler_json(url, "/api/quarentena")["itens"]}
    assert not restantes & {itens["um.bin"]["id"], itens["dois.bin"]["id"]}
    assert pedir(url, "/api/apagar", {"id": itens["dois.bin"]["id"]})[0] == 404


@pytest.mark.parametrize("rota", ["/api/devolver", "/api/apagar", "/api/cacar", "/api/atualizar"])
def test_acoes_so_aceitam_json(url, rota, monkeypatch):
    monkeypatch.setattr(servidor, "cacar", lambda: pytest.fail("não devia caçar"))
    monkeypatch.setattr(servidor, "atualizar_bases", lambda: pytest.fail("não devia atualizar"))
    assert pedir(url, rota, {"id": "../../etc/passwd"}, "text/plain")[0] == 415


@pytest.mark.parametrize("id_", ["../../etc/passwd", "0123456789ab", None])
def test_apagar_recusa_id_que_a_quarentena_nao_deu(url, id_):
    assert pedir(url, "/api/apagar", {"id": id_})[0] == 404


def test_estado_do_painel(url, monkeypatch):
    from guardiao.launcher import estado

    def falso(unidade, usuario, campos):
        if unidade == estado.PROTETOR:
            return {"LoadState": "loaded", "ActiveState": "inactive", "InactiveEnterTimestamp": "@1794060984"}
        if unidade.endswith(".timer"):
            return {"NextElapseUSecRealtime": "@1794152573"}
        return {"LoadState": "loaded", "ActiveState": "active", "ActiveEnterTimestamp": "@1794000000"}

    monkeypatch.setattr(estado, "_systemctl", falso)
    monkeypatch.setattr(estado.montar, "__defaults__", (falso,))
    dados = ler_json(url, "/api/estado")
    assert dados["protetor"] == {"instalado": True, "ativo": False, "desde": 1794060984.0,
                                 "ligar": estado.LIGAR_PROTETOR}
    assert dados["monitor"]["ativo"] and dados["proximas"]["rapida"] == 1794152573.0
    assert dados["cacada"] is None and "avisos" in dados["bases"]


def test_servico_que_nao_existe():
    from guardiao.launcher import estado
    assert estado.servico("x.service", True, lambda *a: {"LoadState": "not-found"})["instalado"] is False
    assert estado.servico("x.service", True, lambda *a: {})["instalado"] is False


def test_cacada_fica_guardada_no_estado(url, monkeypatch):
    from guardiao import cacador
    from pathlib import Path
    monkeypatch.setattr(cacador, "cacar", lambda julgar: [
        cacador.Achado("alta", "systemd", Path("/tmp/x.service"), "roda /tmp/.x a cada login"),
        cacador.Achado("info", "ssh", Path("/tmp/y"), "só informativo")])
    status, resposta = pedir(url, "/api/cacar")
    assert status == 200 and [a["gravidade"] for a in resposta["achados"]] == ["alta"]
    assert ler_json(url, "/api/estado")["cacada"]["achados"][0]["arquivo"] == "/tmp/x.service"
    servidor.CACADA.clear()


def test_suspeito_pendente_so_da_ultima_varredura(url, tmp_path):
    from datetime import datetime

    from guardiao import historico, varredura
    arq = tmp_path / "estranho.sh"
    arq.write_text("x")
    sha = scanner.calcular_sha256(arq)
    suspeito = historico.achado(scanner.Resultado(arq, sha, pontuacao=60, camada="heuristica"))
    resumo = varredura.Resumo(analisados=1, suspeitos=1)
    historico.registrar(historico.novo("rápida", "agendada", datetime(2026, 11, 5, 12, 30), resumo, [suspeito]))
    assert [p["veredito"] for p in ler_json(url, "/api/historico")["pendentes"]] == ["suspeito"]
    historico.registrar(historico.novo("rápida", "agendada", datetime(2026, 11, 6, 12, 30),
                                       varredura.Resumo(analisados=1), []))
    assert ler_json(url, "/api/historico")["pendentes"] == []
