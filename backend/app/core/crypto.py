from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Same volume as the sqlite DB file (settings.database_url defaults to
# /data/db.sqlite3) so the master key and the encrypted tokens it protects
# share one lifecycle: whatever wipes one wipes the other (specs/007
# research.md §2).
_KEY_FILE_PATH = Path("/data/token_key")


def _load_or_generate_key() -> bytes:
    env_key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode()

    if _KEY_FILE_PATH.exists():
        return _KEY_FILE_PATH.read_bytes()

    key = Fernet.generate_key()
    _KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE_PATH.write_bytes(key)
    return key


def ensure_master_key() -> None:
    """Called once at app startup (main.py lifespan) so the key file is
    created before any concurrent source-registration request could race on
    "file doesn't exist yet" and generate two different keys."""
    _load_or_generate_key()


def encrypt_token(plaintext: str) -> str:
    return Fernet(_load_or_generate_key()).encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str | None:
    """Returns None (rather than raising) when the ciphertext can't be
    decrypted with the current master key — e.g. the key file was lost. The
    caller (token_resolver.resolve_access_token) treats that the same as "no
    per-source token" and falls back to the global env token."""
    try:
        return Fernet(_load_or_generate_key()).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None
