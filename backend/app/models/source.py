from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

SourceType = Literal["local", "github", "gitlab", "http", "localhost"]
SourceStatus = Literal["active", "error", "syncing"]
SourceIcon = Literal[
    "📁", "📦", "🐙", "🌐", "💻", "📚", "🚀", "🔧",
    "📝", "🗂️", "⭐", "🔥", "🎯", "📊", "🧩", "🔒",
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
        )
