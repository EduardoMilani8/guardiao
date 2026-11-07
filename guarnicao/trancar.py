"""Trancar um achado: o mesmo para o botão do painel e o do aviso no canto.

Só tranca se o arquivo ainda é exatamente o que foi analisado (mesmo hash, não
é link): se ele mudou, a decisão precisa ser tomada de novo.
"""

from pathlib import Path

from . import historico, quarentena, scanner


class Recusa(Exception):
    def __init__(self, status: int, motivo: str):
        super().__init__(motivo)
        self.status, self.motivo = status, motivo


def trancar(caminho: str, sha256: str, ameaca: str | None = None, camada: str | None = None,
            veredito: str = "ameaca") -> str:
    arquivo = Path(caminho)
    if not arquivo.is_file() or arquivo.is_symlink():
        raise Recusa(410, "o arquivo não está mais lá")
    try:
        if scanner.calcular_sha256(arquivo) != sha256:
            raise Recusa(409, "o arquivo mudou desde a varredura: varra de novo")
        motivo = ameaca or ("suspeito" if veredito == "suspeito" else "ameaça")
        id_cela = quarentena.isolar(arquivo, sha256, motivo, camada=camada, veredito=veredito)
    except PermissionError:
        raise Recusa(403, "sem permissão: é um arquivo do sistema, use "
                          "sudo .venv/bin/python -m guarnicao varrer --isolar")
    except OSError as erro:
        raise Recusa(500, erro.strerror or str(erro))
    historico.marcar_isolado(caminho, sha256, id_cela)
    return id_cela


def do_historico(caminho: str, sha256: str) -> dict:
    """O nome da ameaça e a camada, se o achado está no histórico."""
    for registro in historico.listar(None):
        for a in registro.achados:
            if a.get("caminho") == caminho and a.get("sha256") == sha256:
                return {"ameaca": a.get("ameaca"), "camada": a.get("camada"),
                        "veredito": a.get("veredito") or "ameaca"}
    return {}


def conferir(caminho: str, sha256: str) -> dict:
    """O que a Guarnição sabe deste arquivo, ou Recusa se ela não o acusa.

    O botão Trancar chega por um aviso, e qualquer programa da sessão consegue
    mandar um aviso com o nome da Guarnição. Então quem decide é ela: um achado
    do histórico, ou o arquivo analisado de novo agora (o que também guarda o
    nome da ameaça quando o aviso veio do monitor ou do protetor).
    """
    if dados := do_historico(caminho, sha256):
        return dados
    arquivo = Path(caminho)
    if not arquivo.is_file() or arquivo.is_symlink():
        raise Recusa(410, "o arquivo não está mais lá")
    from . import assinaturas, clamav, regras_yara
    try:
        r = scanner.analisar(arquivo, assinaturas.carregar(), regras_yara.carregar(), clamav.conectar())
    except OSError as erro:
        raise Recusa(500, erro.strerror or str(erro))
    if r.sha256 != sha256:
        raise Recusa(409, "o arquivo mudou desde a varredura: varra de novo")
    if not (r.infectado or r.suspeito):
        raise Recusa(422, "a Guarnição não acha nada neste arquivo agora: abra o painel")
    return {"ameaca": r.ameaca, "camada": r.camada, "veredito": "ameaca" if r.infectado else "suspeito"}
