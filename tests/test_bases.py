import io
import urllib.request

import pytest

from guardiao import bases


class Falsa(bases.Base):
    nome = "falsa"
    intervalo = 3600

    def __init__(self):
        self.publicada = "v1"
        self.falhar_download = False
        self.corrompida = False

    def baixar(self, destino, versao_atual):
        if self.falhar_download:
            raise OSError("rede caiu")
        if versao_atual == self.publicada:
            return None
        (destino / "regras.txt").write_text("corrompida" if self.corrompida else f"regras {self.publicada}")
        return self.publicada

    def validar(self, pasta):
        if (pasta / "regras.txt").read_text() == "corrompida":
            raise bases.ErroDeBase("não compila")


def conteudo():
    return (bases.atual("falsa") / "regras.txt").read_text()


def test_primeira_atualizacao():
    [r] = bases.atualizar([Falsa()], agora=1000)
    assert r.situacao == "atualizada" and conteudo() == "regras v1"
    assert bases.ler_estado("falsa").versao == "v1"


def test_respeita_o_intervalo_e_forcar_ignora():
    base = Falsa()
    bases.atualizar([base], agora=1000)
    base.publicada = "v2"
    assert bases.atualizar([base], agora=1000 + 60)[0].situacao == "em dia"
    assert bases.atualizar([base], forcar=True, agora=1000 + 120)[0].situacao == "atualizada"


def test_sem_novidades_nao_cria_versao():
    base = Falsa()
    bases.atualizar([base], agora=1000)
    assert bases.atualizar([base], agora=1000 + 7200)[0].situacao == "sem novidades"
    assert len(list((bases.pasta_da(base) / "versoes").iterdir())) == 1
    assert bases.ler_estado(base).verificado == 1000 + 7200   # conferida, mesmo sem mudar


def test_troca_e_guarda_so_duas_versoes():
    base = Falsa()
    for i, versao in enumerate(["v1", "v2", "v3"]):
        base.publicada = versao
        bases.atualizar([base], agora=1000 + i * 7200)
    assert conteudo() == "regras v3"
    assert len(list((bases.pasta_da(base) / "versoes").iterdir())) == 2


@pytest.mark.parametrize("problema", ["falhar_download", "corrompida"])
def test_falha_mantem_a_versao_anterior(problema):
    base = Falsa()
    bases.atualizar([base], agora=1000)
    base.publicada = "v2"
    setattr(base, problema, True)
    [r] = bases.atualizar([base], agora=1000 + 7200)
    assert r.situacao == "erro" and r.estado.erro
    assert conteudo() == "regras v1" and bases.ler_estado(base).versao == "v1"
    # Nenhuma sobra de download pela metade.
    assert [p.name for p in (bases.pasta_da(base) / "versoes").iterdir() if p.name.startswith(".")] == []


def test_erro_tenta_de_novo_sem_esperar_o_intervalo():
    base = Falsa()
    base.falhar_download = True
    bases.atualizar([base], agora=1000)
    base.falhar_download = False
    assert bases.atualizar([base], agora=1000 + 60)[0].situacao == "atualizada"


def test_duas_atualizacoes_ao_mesmo_tempo():
    with bases.trava():
        with pytest.raises(bases.Ocupado):
            bases.atualizar([Falsa()])


def test_versao_entra_na_versao_do_motor():
    base = Falsa()
    antes = bases.versoes_em_uso([base])
    bases.atualizar([base], agora=1000)
    assert bases.versoes_em_uso([base]) != antes


def test_download_so_por_https(tmp_path):
    with pytest.raises(bases.ErroDeBase):
        bases.baixar_arquivo("http://exemplo.com/regras.zip", tmp_path / "x")


def test_download_com_limite_de_tamanho(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"x" * 5000))
    with pytest.raises(bases.ErroDeBase):
        bases.baixar_arquivo("https://exemplo.com/enorme", tmp_path / "x", limite=1000)
    sha = bases.baixar_arquivo("https://exemplo.com/ok", tmp_path / "y", limite=10_000)
    assert len(sha) == 64 and (tmp_path / "y").stat().st_size == 5000
