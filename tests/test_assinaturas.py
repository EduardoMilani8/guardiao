import hashlib
import threading

from guardiao import assinaturas, cache, varredura

SHA_RUIM = hashlib.sha256(b"programa malicioso de mentira").hexdigest()


def banco_com(tmp_path, pares, nome="hashes.sqlite"):
    caminho = tmp_path / nome
    assinaturas.criar_sqlite(caminho, pares)
    return caminho


def test_consulta_o_sqlite_e_o_txt(tmp_path):
    fonte = banco_com(tmp_path, [(SHA_RUIM.upper(), "Trojan.Teste")])   # maiúsculas viram minúsculas
    banco = assinaturas.Banco({"aa" * 32: "Local"}, fontes=[fonte])
    assert banco.get(SHA_RUIM) == "Trojan.Teste"
    assert banco.get("aa" * 32) == "Local"
    assert banco.get("bb" * 32) is None
    assert len(banco) == 2


def test_banco_corrompido_nao_derruba_os_outros(tmp_path):
    estragado = tmp_path / "estragado.sqlite"
    estragado.write_bytes(b"isto nao e sqlite" * 100)
    bom = banco_com(tmp_path, [(SHA_RUIM, "Trojan.Teste")])
    banco = assinaturas.Banco({}, fontes=[estragado, bom])
    assert banco.get(SHA_RUIM) == "Trojan.Teste"


def test_enxerga_base_nova_sem_reiniciar(tmp_path, monkeypatch):
    fontes = []
    banco = assinaturas.Banco({}, fontes=lambda: list(fontes))
    assert banco.get(SHA_RUIM) is None
    fontes.append(banco_com(tmp_path, [(SHA_RUIM, "Trojan.Teste")]))   # o timer atualizou
    monkeypatch.setattr(assinaturas, "RECONFERIR_BASES", 0)
    assert banco.get(SHA_RUIM) == "Trojan.Teste"


def test_funciona_em_outra_thread(tmp_path):
    # O monitor cria o banco numa thread e analisa em outra.
    banco = assinaturas.Banco({}, fontes=[banco_com(tmp_path, [(SHA_RUIM, "Trojan.Teste")])])
    achado = []
    t = threading.Thread(target=lambda: achado.append(banco.get(SHA_RUIM)))
    t.start()
    t.join()
    assert achado == ["Trojan.Teste"]


def test_hash_novo_pega_arquivo_que_estava_no_cache(tmp_path, monkeypatch):
    pasta = tmp_path / "p"
    pasta.mkdir()
    (pasta / "programa").write_bytes(b"programa malicioso de mentira")
    fontes = []
    monkeypatch.setattr(assinaturas, "_fontes_das_bases", lambda: list(fontes))
    versao = "fixa"   # hashes novos não mudam a versão do motor: o cache continua valendo
    monkeypatch.setattr(cache, "versao_motor", lambda: versao)

    primeira = [i for i in varredura.executar([pasta], varredura.Exclusoes(), processos=1)][-1]
    assert (primeira.analisados, primeira.ameacas) == (1, 0)

    fontes.append(banco_com(tmp_path, [(SHA_RUIM, "Trojan.Teste")]))   # MalwareBazaar trouxe o hash
    segunda = [i for i in varredura.executar([pasta], varredura.Exclusoes(), processos=1)][-1]
    assert (segunda.em_cache, segunda.ameacas) == (0, 1)

    # E um arquivo limpo de verdade continua sendo pulado.
    (pasta / "notas.txt").write_text("nada aqui")
    list(varredura.executar([pasta], varredura.Exclusoes(), processos=1))
    terceira = [i for i in varredura.executar([pasta], varredura.Exclusoes(), processos=1)][-1]
    assert (terceira.em_cache, terceira.ameacas) == (1, 1)
