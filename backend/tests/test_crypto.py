from __future__ import annotations

import backend.app.core.crypto as crypto
from cryptography.fernet import Fernet


def test_encrypt_decrypt_round_trip_with_generated_key(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key")

    ciphertext = crypto.encrypt_token("ghp_secret123")

    assert ciphertext != "ghp_secret123"
    assert crypto.decrypt_token(ciphertext) == "ghp_secret123"


def test_generated_key_is_persisted_and_reused(monkeypatch, tmp_path):
    """A key generated on first use must survive process restart — otherwise
    every token encrypted before a restart becomes undecryptable (spec
    FR-010/FR-011)."""
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    key_path = tmp_path / "token_key"
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", key_path)

    ciphertext = crypto.encrypt_token("ghp_secret123")
    assert key_path.exists()
    first_key = key_path.read_bytes()

    # Simulate a fresh process: same file, no in-memory cache to reuse.
    ciphertext_again = crypto.encrypt_token("ghp_secret123")
    assert key_path.read_bytes() == first_key
    assert crypto.decrypt_token(ciphertext) == "ghp_secret123"
    assert crypto.decrypt_token(ciphertext_again) == "ghp_secret123"


def test_env_var_key_takes_priority_over_file(monkeypatch, tmp_path):
    key_path = tmp_path / "token_key"
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", key_path)
    # A stale/different key sits in the file...
    key_path.write_bytes(Fernet.generate_key())
    # ...but the explicit env var must win.
    env_key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", env_key)

    ciphertext = crypto.encrypt_token("ghp_secret123")
    assert Fernet(env_key.encode()).decrypt(ciphertext.encode()) == b"ghp_secret123"


def test_decrypt_with_lost_master_key_returns_none(monkeypatch, tmp_path):
    """Simulates the master-key-loss edge case (spec Edge Cases / FR-011):
    ciphertext encrypted under one key can't be decrypted under another, and
    the caller must get None (not an exception) so it can fall back to the
    global token."""
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key")
    ciphertext = crypto.encrypt_token("ghp_secret123")

    # A different key file (simulates the volume holding the key being reset).
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key_new")

    assert crypto.decrypt_token(ciphertext) is None
