import os

from guarnicao import cache as cache_mod

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


def test_cache_vence_quando_o_clamav_aparece_mas_nao_a_cada_assinatura(monkeypatch):
    class ClamAVFalso:
        def __init__(self, motor, assinaturas):
            self.motor, self.assinaturas = motor, assinaturas

        def versao(self):
            return self.motor, self.assinaturas, None

    def com(cliente):
        monkeypatch.setattr(cache_mod.clamav, "conectar", lambda: cliente)
        return cache_mod.versao_motor()

    sem = com(None)
    hoje = com(ClamAVFalso("ClamAV 1.5.4", 28173))
    amanha = com(ClamAVFalso("ClamAV 1.5.4", 28174))
    motor_novo = com(ClamAVFalso("ClamAV 1.6.0", 28174))
    assert sem != hoje        # o ClamAV ainda não viu os arquivos do cache
    assert hoje == amanha     # assinaturas do dia não zeram o cache
    assert amanha != motor_novo


def test_cache_corrompido_nao_quebra_a_varredura(tmp_path):
    with cache_mod.Cache(versao="v1") as c:
        c.db.execute("DROP TABLE limpos")
        assert not c.limpo((tmp_path).stat())
        c.marcar_limpo(tmp_path.stat(), "0" * 64)   # sem exceção: só perde o atalho


def test_duas_varreduras_ao_mesmo_tempo_nao_se_esperam(tmp_path):
    # 08/11/2026: com a completa da semana rodando (ela anda devagar e segura a
    # escrita do cache entre um lote e outro), uma varredura pelo painel esperava
    # 10 s em CADA arquivo e parecia travada.
    import time
    arquivos = []
    for i in range(5):
        a = tmp_path / f"a{i}.txt"
        a.write_text(str(i))
        arquivos.append(a)
    caminho = tmp_path / "c.sqlite"
    lenta, outra = cache_mod.Cache(caminho, versao="v1"), cache_mod.Cache(caminho, versao="v1")
    lenta.marcar_limpo(arquivos[0].stat(), "0" * 64)     # abre a escrita e não grava ainda
    inicio = time.monotonic()
    for a in arquivos[1:]:
        outra.marcar_limpo(a.stat(), "0" * 64)
    assert time.monotonic() - inicio < 3
    lenta.fechar()
    outra.fechar()


def test_grava_de_tempos_em_tempos_mesmo_com_poucos_arquivos(tmp_path, monkeypatch):
    # Quem anda devagar não pode segurar a escrita por minutos: grava a cada 2 s.
    import time
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("a")
    b.write_text("b")
    caminho = tmp_path / "c.sqlite"
    lenta = cache_mod.Cache(caminho, versao="v1")
    lenta.marcar_limpo(a.stat(), "0" * 64)
    agora = time.monotonic()
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: agora + 3)
    lenta.marcar_limpo(b.stat(), "0" * 64)
    with cache_mod.Cache(caminho, versao="v1") as leitor:
        assert leitor.limpo(a.stat()) and leitor.limpo(b.stat())
    lenta.fechar()
