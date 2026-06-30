from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:////data/db.sqlite3"
    host_docs_root: str = "/host-docs"
    default_poll_interval: int = 300

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
