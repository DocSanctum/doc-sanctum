from __future__ import annotations

import os

from ..core.crypto import decrypt_token
from ..models.source import Source

_GLOBAL_ENV_VAR = {"github": "GITHUB_TOKEN", "gitlab": "GITLAB_TOKEN"}


def resolve_access_token(source: Source) -> str | None:
    """Per-source token takes priority (spec FR-003); falls back to the
    global env token when there's no source-level token, or when the
    source-level one can't be decrypted (e.g. the master key was lost —
    spec FR-011)."""
    if source.access_token_encrypted is not None:
        token = decrypt_token(source.access_token_encrypted)
        if token is not None:
            return token

    env_var = _GLOBAL_ENV_VAR.get(source.type)
    return os.getenv(env_var) if env_var else None
