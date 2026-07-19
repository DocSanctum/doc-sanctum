"""Run once, before the vectorstore server starts (see the vectorstore-vacuum
service in docker-compose.yml) — never against a running server, since it
opens chroma.sqlite3 directly and Chroma's own `chroma vacuum` CLI errors out
if the file is already locked by a live server.

Two independent problems, confirmed by hand against a real Chroma 1.x
server, neither of which Chroma cleans up on its own in single-node mode:

1. delete_collection() removes the collection's rows from chroma.sqlite3 but
   never removes its on-disk HNSW segment directory (data_level0.bin and
   friends) — every deleted collection leaks its full vector index on disk
   forever. This is the dominant source of unbounded disk growth from
   repeated source remove/re-add cycles, and `chroma vacuum` does not touch
   it either (verified: running it only shrinks chroma.sqlite3 itself).
   Fixed here by deleting any segment directory no longer referenced by the
   `segments` table.
2. chroma.sqlite3 itself only frees space via SQLite's own freelist
   mechanism, which VACUUM must be run to reclaim. VACUUM rewrites the
   entire file regardless of how much is actually reclaimable, so it's
   gated on the freelist ratio here rather than run unconditionally on
   every startup — an unchanged installation with nothing to reclaim would
   otherwise pay a full-file-rewrite cost on every restart for no benefit.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

DATA_DIR = Path("/data")
DB_PATH = DATA_DIR / "chroma.sqlite3"

# Only ever remove directories that look like a segment id, never anything
# else Chroma's on-disk layout might contain now or in the future.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

_VACUUM_FREELIST_RATIO_THRESHOLD = 0.15
_VACUUM_MIN_RECLAIMABLE_BYTES = 5 * 1024 * 1024


def _delete_orphaned_segment_dirs(conn: sqlite3.Connection) -> None:
    live_ids = {row[0] for row in conn.execute("SELECT id FROM segments")}
    removed_count = 0
    freed_bytes = 0
    for entry in DATA_DIR.iterdir():
        if not entry.is_dir() or not _UUID_RE.match(entry.name):
            continue
        if entry.name in live_ids:
            continue
        freed_bytes += sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
        shutil.rmtree(entry)
        removed_count += 1
    if removed_count:
        print(
            f"vectorstore-maintenance: removed {removed_count} orphaned segment "
            f"director{'y' if removed_count == 1 else 'ies'}, "
            f"freed {freed_bytes / 1024 / 1024:.1f} MiB"
        )


def _vacuum_if_worthwhile(conn: sqlite3.Connection) -> None:
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    if not page_count:
        return
    freelist_count = conn.execute("PRAGMA freelist_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    reclaimable_bytes = freelist_count * page_size
    ratio = freelist_count / page_count
    if (
        ratio < _VACUUM_FREELIST_RATIO_THRESHOLD
        or reclaimable_bytes < _VACUUM_MIN_RECLAIMABLE_BYTES
    ):
        return
    print(
        f"vectorstore-maintenance: vacuuming chroma.sqlite3 "
        f"({reclaimable_bytes / 1024 / 1024:.1f} MiB reclaimable, {ratio:.0%} of file)"
    )
    conn.execute("VACUUM")
    conn.execute(
        "INSERT INTO maintenance_log (operation, timestamp) VALUES ('vacuum', CURRENT_TIMESTAMP)"
    )
    conn.commit()


def main() -> None:
    if not DB_PATH.exists():
        return  # fresh volume — nothing has been written yet
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        _delete_orphaned_segment_dirs(conn)
        _vacuum_if_worthwhile(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Best-effort maintenance — never block the vectorstore service (and
        # therefore the whole app) from starting over a cleanup failure.
        print(f"vectorstore-maintenance: skipped due to error: {exc}")
