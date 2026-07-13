from __future__ import annotations

import backend.app.api.deployment as deployment_module
import backend.app.api.sources as sources_module
import backend.app.main as main_module
import pytest
from backend.app.core.config import settings
from fastapi import HTTPException

# --- A vector store connection failure at startup must NOT crash the whole
# app in either deployment mode — only semantic search is affected, the
# rest of the app (sources, keyword search, etc.) keeps starting. This
# replaces the old scaleout-only fail-fast behavior, since standalone now
# also depends on the shared vector store. ---


@pytest.mark.asyncio
async def test_lifespan_survives_init_engine_failure(monkeypatch):
    """main.lifespan calls init_engine() unguarded, but init_engine() itself
    (backend/app/vectorstore/client.py) never raises — it catches connection
    failures internally and reports unavailability via is_engine_available(),
    so a vector-store outage must not prevent the rest of the app from
    starting."""

    async def fake_create_tables():
        return None

    def failing_init_engine():
        return False

    async def fake_start_polling_all():
        return None

    monkeypatch.setattr(main_module, "create_tables", fake_create_tables)
    # Master-key generation and check_and_recover() both touch /data —
    # irrelevant to this test's focus and not writable in a sandboxed test
    # environment.
    monkeypatch.setattr(main_module, "ensure_master_key", lambda: None)
    monkeypatch.setattr(main_module, "init_engine", failing_init_engine)
    monkeypatch.setattr(main_module, "check_and_recover", lambda: _noop_coro())
    monkeypatch.setattr(main_module, "start_polling_all", fake_start_polling_all)
    monkeypatch.setattr(main_module, "resume_local_sources", lambda: _noop_coro())
    monkeypatch.setattr(main_module, "seed_sample_source", lambda: _noop_coro())

    async with main_module.lifespan(main_module.app):
        pass  # must not raise even though init_engine reported failure


async def _noop_coro() -> None:
    return None


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
