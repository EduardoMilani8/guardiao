import os

from guardiao import cache as cache_mod

EICAR = "".join(["X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"])


def test_cache_percebe_conteudo_novo_mesmo_com_mtime_falso(tmp_path):
    arquivo = tmp_path / "relatorio.txt"
    arquivo.write_text("relatório inocente")
    with cache_mod.Cache(versao="v1") as c:
        c.marcar_limpo(arquivo.stat(), "0" * 64)
        mtime_antigo = arquivo.stat().st_mtime_ns
        arquivo.write_text(EICAR)
        os.utime(arquivo, ns=(mtime_antigo, mtime_antigo))   # como um `touch -d` do atacante
        assert not c.limpo(arquivo.stat())                   # o ctime denuncia


def test_cache_invalida_quando_o_motor_muda(tmp_path):
    arquivo = tmp_path / "a.txt"
    arquivo.write_text("x")
    caminho = tmp_path / "c.sqlite"
    with cache_mod.Cache(caminho, versao="v1") as c:
        c.marcar_limpo(arquivo.stat(), "0" * 64)
        assert c.limpo(arquivo.stat())
    with cache_mod.Cache(caminho, versao="v2") as c:   # ex.: regra YARA nova
        assert not c.limpo(arquivo.stat())


def test_cache_corrompido_nao_quebra_a_varredura(tmp_path):
    with cache_mod.Cache(versao="v1") as c:
        c.db.execute("DROP TABLE limpos")
        assert not c.limpo((tmp_path).stat())
        c.marcar_limpo(tmp_path.stat(), "0" * 64)   # sem exceção: só perde o atalho
