from __future__ import annotations

import backend.app.core.crypto as crypto
from backend.app.models.source import Source
from backend.app.services.token_resolver import resolve_access_token


def _make_source(**overrides) -> Source:
    defaults = dict(name="repo", type="github", path="https://github.com/owner/repo")
    defaults.update(overrides)
    return Source(**defaults)


def test_prefers_source_level_token_over_global(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key")
    monkeypatch.setenv("GITHUB_TOKEN", "global-token")

    encrypted = crypto.encrypt_token("source-level-token")
    source = _make_source(access_token_encrypted=encrypted)

    assert resolve_access_token(source) == "source-level-token"


def test_falls_back_to_global_token_when_no_source_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "global-token")
    source = _make_source(access_token_encrypted=None)

    assert resolve_access_token(source) == "global-token"


def test_falls_back_to_gitlab_global_token_for_gitlab_type(monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "global-gitlab-token")
    source = _make_source(type="gitlab", path="https://gitlab.com/group/project")

    assert resolve_access_token(source) == "global-gitlab-token"


def test_returns_none_when_no_source_and_no_global_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    source = _make_source(access_token_encrypted=None)

    assert resolve_access_token(source) is None


def test_falls_back_to_global_when_source_token_undecryptable(monkeypatch, tmp_path):
    """Master-key-loss scenario (spec FR-011): a source-level token that can
    no longer be decrypted must not surface as an error here — it should
    behave exactly like "no source-level token"."""
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key")
    encrypted = crypto.encrypt_token("source-level-token")

    # Simulate the master key being lost/rotated.
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key_new")
    monkeypatch.setenv("GITHUB_TOKEN", "global-token")

    source = _make_source(access_token_encrypted=encrypted)
    assert resolve_access_token(source) == "global-token"
