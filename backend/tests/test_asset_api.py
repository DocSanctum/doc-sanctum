from __future__ import annotations

import backend.app.core.database as database_module
import httpx
import pytest
import pytest_asyncio
from backend.app.api import files as files_module
from backend.app.core.database import create_tables, get_session
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-body"


@pytest_asyncio.fixture
async def client(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "async_session_factory", factory)
    await create_tables()

    docs = tmp_path / "docs"
    (docs / "guide" / "images").mkdir(parents=True)
    (docs / "guide" / "intro.md").write_text("![diagram](images/arch.png)\n")
    (docs / "guide" / "images" / "arch.png").write_bytes(PNG_BYTES)
    (docs / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (docs / ".env").write_text("SECRET=1\n")
    (tmp_path / "outside.png").write_bytes(PNG_BYTES)
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id, name, type, path, created_at) "
                "VALUES ('src1', 'Docs', 'local', :p, '2026-01-01')"
            ),
            {"p": str(docs)},
        )
        await session.commit()

    app = FastAPI()
    app.include_router(files_module.router, prefix="/api/v1")

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c
    await engine.dispose()


@pytest.mark.asyncio
async def test_markdown_embedded_image_is_served_with_its_media_type(client):
    res = await client.get(
        "/api/v1/sources/src1/asset", params={"path": "guide/images/arch.png"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content == PNG_BYTES


@pytest.mark.asyncio
async def test_svg_is_sandboxed_so_it_cannot_run_scripts(client):
    res = await client.get("/api/v1/sources/src1/asset", params={"path": "logo.svg"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [".env", "guide/intro.md", "missing.png"])
async def test_non_image_or_missing_files_are_not_served(client, path):
    res = await client.get("/api/v1/sources/src1/asset", params={"path": path})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_image_outside_the_source_root_is_not_served(client):
    res = await client.get(
        "/api/v1/sources/src1/asset", params={"path": "../outside.png"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unknown_source_returns_404(client):
    res = await client.get("/api/v1/sources/nope/asset", params={"path": "a.png"})
    assert res.status_code == 404
