from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS source (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                polling_interval_seconds INTEGER,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                error_message TEXT
            )
        """)
        )
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS setting (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        )


async def get_setting(key: str, default: str | None = None) -> str | None:
    async with async_session_factory() as session:
        row = await session.execute(text("SELECT value FROM setting WHERE key = :k"), {"k": key})
        result = row.scalar_one_or_none()
        return result if result is not None else default


async def set_setting(key: str, value: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("INSERT INTO setting(key, value) VALUES(:k, :v) ON CONFLICT(key) DO UPDATE SET value=:v"),
            {"k": key, "v": value},
        )
        await session.commit()
