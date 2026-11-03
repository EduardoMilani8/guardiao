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
    with urllib.request.urlopen(url, timeout=20) as resposta:
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
    arquivos = [e for e in evs if e["tipo"] == "arquivo"]
    assert len(arquivos) == evs[0]["total"] == 10
    assert evs[-1]["ameaca"] >= 1 and evs[-1]["suspeito"] >= 1


def test_pagina_e_estaticos(url):
    with urllib.request.urlopen(f"{url}/", timeout=5) as r:
        assert b"Guardi" in r.read()
    for nome in servidor.ESTATICOS:
        with urllib.request.urlopen(f"{url}/estatico/{nome}", timeout=5) as r:
            assert r.status == 200


@pytest.mark.parametrize("caminho", [
    "/api/varrer?alvo=/etc",                # alvo só por nome, nunca caminho
    "/api/varrer",
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
