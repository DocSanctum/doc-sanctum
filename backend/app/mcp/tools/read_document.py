import json
import os

import httpx
from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...services.github import _github_headers, _parse_github_url


async def _read_local(source: Source, path: str) -> str:
    expanded = os.path.expanduser(source.path)
    safe_root = os.path.realpath(expanded)
    target = os.path.realpath(os.path.join(expanded, path))
    if not target.startswith(safe_root + os.sep) and target != safe_root:
        raise ValueError("Access denied: path traversal detected")
    if not os.path.isfile(target):
        raise ValueError(f"File not found: {path}")
    with open(target, encoding="utf-8") as f:
        return f.read()


async def _read_github(source: Source, path: str) -> str:
    owner, repo = _parse_github_url(source.path)
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_github_headers())
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _read_http(source: Source, path: str) -> str:
    base = source.path.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def read_document_handler(source_id: str, path: str) -> str:
    """Read the full content of a specific MD file.

    Args:
        source_id: UUID of the source containing the file.
        path: Relative file path from the source root (e.g. guide/intro.md).
    """
    async with async_session_factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
                )
            )
            .mappings()
            .first()
        )

    if not row:
        raise ValueError(f"Source not found: {source_id}")

    source = Source.from_row(dict(row))

    if source.type == "local":
        content = await _read_local(source, path)
    elif source.type == "github":
        content = await _read_github(source, path)
    else:
        content = await _read_http(source, path)

    return json.dumps(
        {
            "path": path,
            "source_id": source.id,
            "source_name": source.name,
            "content": content,
        },
        ensure_ascii=False,
    )
