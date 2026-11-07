"""Onde a Guarnição guarda as coisas."""

import os
import pwd
from pathlib import Path


def casa_real() -> Path:
    """A casa de quem pediu a varredura. Com sudo, HOME vira /root, mas os
    Downloads, a configuração e a quarentena que importam são os do usuário."""
    usuario = os.environ.get("SUDO_USER")
    if os.geteuid() == 0 and usuario:
        try:
            return Path(pwd.getpwnam(usuario).pw_dir)
        except KeyError:
            pass
    return Path.home()


NOME = "guarnicao"
NOME_ANTIGO = "guardiao"   # o projeto se chamava Guardião até novembro de 2026

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", casa_real() / ".config")) / NOME / "config.toml"


def variavel(nome: str) -> str | None:
    """GUARNICAO_<nome> do ambiente; o GUARDIAO_<nome> antigo ainda vale."""
    return os.environ.get(f"GUARNICAO_{nome}") or os.environ.get(f"GUARDIAO_{nome}") or None


def migrar(casa: Path | None = None, ambiente=os.environ) -> list[Path]:
    """Leva as pastas do nome antigo para o novo: ~/.config/guardiao vira
    ~/.config/guarnicao, e igual para ~/.local/share e ~/.cache.

    No lugar da antiga fica um atalho para a nova, para um serviço da versão
    anterior que ainda esteja rodando continuar achando tudo até ser trocado.
    Só move quando a nova ainda não existe: rodar de novo não faz nada.
    Devolve as pastas novas criadas assim."""
    casa = casa or casa_real()
    lugares = [ambiente.get("XDG_CONFIG_HOME") or casa / ".config",
               ambiente.get("XDG_DATA_HOME") or casa / ".local" / "share",
               ambiente.get("XDG_CACHE_HOME") or casa / ".cache"]
    movidas = []
    for lugar in map(Path, lugares):
        antiga, nova = lugar / NOME_ANTIGO, lugar / NOME
        # is_symlink primeiro: o atalho deixado por uma migração anterior não se move de novo.
        if antiga.is_symlink() or not antiga.is_dir() or nova.exists() or nova.is_symlink():
            continue
        try:
            antiga.rename(nova)          # mesma pasta, mesmo disco: atômico, mantém dono e permissões
        except OSError:
            continue
        try:
            antiga.symlink_to(NOME)      # relativo: guardiao -> guarnicao
        except OSError:
            pass
        movidas.append(nova)
    return movidas


def ler_config(arquivo: Path | None = None) -> dict:
    import tomllib
    try:
        return tomllib.loads((arquivo or CONFIG).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
