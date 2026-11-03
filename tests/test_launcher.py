import json
import threading
import urllib.error
import urllib.request

import pytest

from guardiao import assinaturas, eventos, regras_yara, scanner
from guardiao.launcher import demo, servidor


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


def test_varredura_demo_transmitida(url):
    evs = ler_eventos(f"{url}/api/varrer?alvo=demo")
    assert evs[0]["tipo"] == "inicio" and evs[-1]["tipo"] == "fim"
    assert evs[-1]["total"] == 10 and evs[-1]["em_cache"] == 0   # a demonstração nunca usa o cache
    assert evs[-1]["ameaca"] >= 1 and evs[-1]["suspeito"] >= 1
    # Arquivos limpos não geram evento próprio: só achados, e o progresso em lotes.
    achados = [e for e in evs if e["tipo"] == "arquivo"]
    assert len(achados) == evs[-1]["ameaca"] + evs[-1]["suspeito"]
    assert all(e["veredito"] != "limpo" for e in achados)
    assert any(e["tipo"] == "progresso" for e in evs)


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
    assert evs[-1]["tipo"] == "fim" and evs[-1]["ameaca"] >= 1


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
    pedido = urllib.request.Request(f"{url}/api/varrer?alvo=demo", headers={"Host": "malicioso.com:80"})
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
