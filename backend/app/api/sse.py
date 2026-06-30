import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..services.watcher import start_watching, get_queue

router = APIRouter(tags=["sse"])


@router.get("/sse/sources/{source_id}")
async def sse_source(source_id: str, session: AsyncSession = Depends(get_session)):
    row = (await session.execute(
        text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")

    source = dict(row)
    if source["type"] == "local":
        start_watching(source_id, source["path"])

    async def event_stream():
        yield "data: {}\n\n"  # initial ping
        queue = get_queue(source_id)
        while True:
            if queue:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {payload['event']}\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            else:
                await asyncio.sleep(30)
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
