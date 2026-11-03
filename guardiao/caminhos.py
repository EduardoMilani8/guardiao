"""Onde o Guardião guarda as coisas."""

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


CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", casa_real() / ".config")) / "guardiao" / "config.toml"


def ler_config(arquivo: Path | None = None) -> dict:
    import tomllib
    try:
        return tomllib.loads((arquivo or CONFIG).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
