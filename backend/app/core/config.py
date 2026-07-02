from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:////data/db.sqlite3"
    host_docs_root: str = "/host-docs"
    default_poll_interval: int = 300

    # Deployment mode (specs/004-scaleout-deployment). "standalone": single
    # instance, in-memory vector index, local sources allowed (default,
    # backward-compatible with 003). "scaleout": shared/persistent vector
    # store via vector_store_host/port, local sources rejected.
    deployment_mode: Literal["standalone", "scaleout"] = "standalone"
    vector_store_host: str | None = None
    vector_store_port: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
