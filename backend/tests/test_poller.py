from __future__ import annotations

import asyncio

import backend.app.services.poller as poller_module
import pytest

pytestmark = pytest.mark.asyncio


async def test_stop_polling_cancels_and_removes_the_recurring_task():
    """Before stop_polling existed, nothing ever removed a source's entry
    from _tasks or cancelled it on delete — a deleted source's poller kept
    running forever, resyncing (and recreating the vector collection for) a
    source that no longer exists."""

    async def loop_forever():
        while True:
            await asyncio.sleep(0.01)

    task = asyncio.create_task(loop_forever())
    poller_module._tasks["src-1"] = task

    await poller_module.stop_polling("src-1")

    assert "src-1" not in poller_module._tasks
    assert task.cancelled()


async def test_stop_polling_is_a_noop_for_an_untracked_source():
    await poller_module.stop_polling("never-registered")  # must not raise
