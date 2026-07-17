from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

SourceType = Literal["local", "github", "gitlab", "http", "localhost"]
# "partial": the source registered and its tree listed, but some documents
# could not be indexed (e.g. a transient rate limit on their content fetch).
# The source is usable but incomplete; the next poll re-attempts the missing
# documents. Distinct from "error" (nothing usable) so the UI can flag it
# without hiding the source entirely.
SourceStatus = Literal["active", "error", "syncing", "partial"]
SourceIcon = Literal[
    "📁",
    "📦",
    "🐙",
    "🌐",
    "💻",
    "📚",
    "🚀",
    "🔧",
    "📝",
    "🗂️",
    "⭐",
    "🔥",
    "🎯",
    "📊",
    "🧩",
    "🔒",
    "📖",
    "🗃️",
    "💾",
    "☁️",
    "🐳",
    "💡",
    "🏷️",
    "📌",
]


@dataclass
class Source:
    name: str
    type: SourceType
    path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    polling_interval_seconds: int | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: SourceStatus = "active"
    error_message: str | None = None
    icon: SourceIcon | None = None
    # Encrypted (never plaintext) per-source access token — see
    # backend/app/core/crypto.py and services/token_resolver.py. Excluded
    # from to_dict(); only its presence is exposed via access_token_configured.
    access_token_encrypted: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "polling_interval_seconds": self.polling_interval_seconds,
            "created_at": self.created_at,
            "status": self.status,
            "error_message": self.error_message,
            "icon": self.icon,
            "access_token_configured": self.access_token_encrypted is not None,
        }

    @classmethod
    def from_row(cls, row: dict) -> Source:
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            path=row["path"],
            polling_interval_seconds=row["polling_interval_seconds"],
            created_at=row["created_at"],
            status=row["status"],
            error_message=row["error_message"],
            icon=row.get("icon"),
            access_token_encrypted=row.get("access_token_encrypted"),
        )
