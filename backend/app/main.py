from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import files, sources, sse
from .core.database import create_tables
from .mcp.server import mcp
from .services.poller import start_polling_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await start_polling_all()
    yield


app = FastAPI(title="MD Doc Browser", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")

app.mount("/mcp", mcp.sse_app())
