from __future__ import annotations

import backend.app.api.deployment as deployment_module
import backend.app.api.sources as sources_module
import backend.app.main as main_module
import pytest
from backend.app.core.config import settings
from fastapi import HTTPException

# --- FR-010: scaleout startup must fail fast on vector store connection failure ---


@pytest.mark.asyncio
async def test_lifespan_propagates_init_engine_failure(monkeypatch):
    """main.lifespan calls init_engine() unguarded — an exception there must
    propagate and fail app startup rather than be swallowed."""

    async def fake_create_tables():
        return None

    def boom():
        raise RuntimeError("cannot reach shared vector store")

    async def fake_start_polling_all():
        return None

    monkeypatch.setattr(main_module, "create_tables", fake_create_tables)
    # Master-key generation (specs/007-source-access-token) writes to
    # /data — irrelevant to this test's focus (init_engine failure
    # propagation) and not writable in a sandboxed test environment.
    monkeypatch.setattr(main_module, "ensure_master_key", lambda: None)
    monkeypatch.setattr(main_module, "init_engine", boom)
    monkeypatch.setattr(main_module, "start_polling_all", fake_start_polling_all)

    with pytest.raises(RuntimeError, match="cannot reach shared vector store"):
        async with main_module.lifespan(main_module.app):
            pass


# --- FR-004, SC-003: scaleout rejects local source registration ---


def test_reject_local_source_in_scaleout_raises_422(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "scaleout")

    with pytest.raises(HTTPException) as exc_info:
        sources_module._reject_local_source_in_scaleout("local")
    assert exc_info.value.status_code == 422


def test_reject_local_source_in_scaleout_allows_remote_types(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "scaleout")

    for source_type in ("github", "http", "localhost"):
        sources_module._reject_local_source_in_scaleout(source_type)  # must not raise


def test_reject_local_source_standalone_allows_local(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "standalone")

    sources_module._reject_local_source_in_scaleout("local")  # must not raise


# --- FR-006: deployment mode is queryable ---


@pytest.mark.asyncio
async def test_get_deployment_status_reflects_settings(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "scaleout")
    status = await deployment_module.get_deployment_status()
    assert status.mode == "scaleout"

    monkeypatch.setattr(settings, "deployment_mode", "standalone")
    status = await deployment_module.get_deployment_status()
    assert status.mode == "standalone"
