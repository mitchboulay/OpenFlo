"""The session-signing secret (FR-15, Security NFR): ``<data dir>/secret.key``, created once with mode 0600 (tightened
at startup if broader)."""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from .. import private_files

logger = logging.getLogger(__name__)

SECRET_FILE = "secret.key"


def load_or_create(data_dir: Path) -> str:
    """Return the persisted secret, generating it on first start. ``O_EXCL`` makes concurrent starts agree."""
    path = data_dir / SECRET_FILE
    private_files.make_dir(data_dir)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, private_files.FILE_MODE)
    except FileExistsError:
        private_files.tighten(path)
        secret = path.read_text(encoding="ascii").strip()
        if not secret:
            raise RuntimeError(f"{path} is empty; delete it to generate a new one (signs everyone out)")
        return secret
    secret = secrets.token_hex(32)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(secret + "\n")
    logger.info("generated session secret at %s", path)
    return secret
