import json
import os
import subprocess
import sys

from guarnicao import andamento, varredura


def test_grava_le_e_apaga(tmp_path):
    arq = tmp_path / "progresso.json"
    andamento.gravar("rápida", 183, 305, arq)
    d = andamento.ler(arq)
    assert (d["tipo"], d["feitos"], d["total"], d["pid"]) == ("rápida", 183, 305, os.getpid())
    andamento.apagar(arq)
    assert andamento.ler(arq) is None


def test_pid_morto_e_ignorado(tmp_path):
    arq = tmp_path / "progresso.json"
    morto = subprocess.Popen([sys.executable, "-c", "pass"])
    morto.wait()
    arq.write_text(json.dumps({"pid": morto.pid, "tipo": "rápida", "feitos": 1, "total": 9}))
    assert andamento.ler(arq) is None          # varredura que morreu não prende o escudo


def test_so_para_processo_de_varredura(tmp_path):
    arq = tmp_path / "progresso.json"
    andamento.gravar("rápida", 1, 9, arq)      # este processo é o pytest, não "guarnicao varrer"
    assert andamento.ler(arq)["pode_parar"] is False
    assert andamento.parar(arq) is False       # nunca mata o launcher nem outro programa


def test_executar_com_rotulo_grava_e_apaga(tmp_path, monkeypatch):
    arq = tmp_path / "progresso.json"
    monkeypatch.setattr(andamento, "ARQUIVO", arq)
    (tmp_path / "pasta").mkdir()
    (tmp_path / "pasta" / "a.txt").write_text("oi")
    vistos = []
    for item in varredura.executar([tmp_path / "pasta"], varredura.Exclusoes(), usar_cache=False,
                                   processos=1, rotulo="rápida"):
        if isinstance(item, varredura.Progresso):
            vistos.append(andamento.ler(arq) is not None)
    assert any(vistos) and not arq.exists()


def test_executar_sem_rotulo_nao_grava(tmp_path, monkeypatch):
    arq = tmp_path / "progresso.json"
    monkeypatch.setattr(andamento, "ARQUIVO", arq)
    (tmp_path / "pasta").mkdir()
    list(varredura.executar([tmp_path / "pasta"], varredura.Exclusoes(), usar_cache=False, processos=1))
    assert not arq.exists()


def test_pid_reaproveitado_por_outro_programa_e_ignorado(tmp_path):
    arq = tmp_path / "progresso.json"
    outro = subprocess.Popen(["sleep", "5"])
    try:
        arq.write_text(json.dumps({"pid": outro.pid, "tipo": "rápida", "feitos": 1, "total": 9}))
        assert andamento.ler(arq) is None      # não é a Guarnição: a varredura de verdade morreu
    finally:
        outro.kill()
