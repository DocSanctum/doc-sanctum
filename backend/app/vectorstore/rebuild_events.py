from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# One distinctly-named file per automatic-rebuild event, stored in the same
# durable volume the rest of the app's state lives in (sqlite_data), so
# incidents survive container replacement the same way the SQLite database
# and Chroma collections do. Never used for an ordinary first-run full
# build — only for genuinely unexpected conditions (model mismatch,
# incomplete-write recovery).
_EVENTS_DIR = Path("/data/vector-index-rebuilds")

_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug(name: str) -> str:
    slug = _SLUG_RE.sub("-", name).strip("-")
    return slug or "source"


def record(
    *,
    source_id: str,
    source_name: str,
    reason: str,
    doc_count: int,
    duration_seconds: float,
    detail: str = "",
) -> Path:
    """Write one rebuild-event record and return its path. First line is a
    one-line summary understandable at a glance; everything after is
    free-form diagnostic detail."""
    _EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"vector-index-rebuild_{_slug(source_name or source_id)}_{timestamp}.log"
    path = _EVENTS_DIR / filename

    summary = (
        f"REBUILT source={source_name or source_id} reason={reason} "
        f"docs={doc_count} duration={duration_seconds:.1f}s"
    )
    body = summary + "\n"
    if detail:
        body += "\n" + detail + "\n"
    path.write_text(body)
    return path
