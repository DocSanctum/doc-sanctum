# Data Model: MD Document Browser

**Feature**: 001-md-doc-browser
**Date**: 2026-06-30

---

## Persisted Entities

### Source

Represents a registered path (local or remote) where MD files are discovered.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `name` | TEXT | NOT NULL | Display label; defaults to last path segment if not provided |
| `type` | TEXT (enum) | NOT NULL | `local` \| `github` \| `http` \| `localhost` |
| `path` | TEXT | NOT NULL, UNIQUE | Filesystem path (local) or base URL (remote) |
| `polling_interval_seconds` | INTEGER | nullable | Remote types only. Default: `github`=600, `http`/`localhost`=300. NULL for local. |
| `created_at` | DATETIME | NOT NULL, default NOW | ISO 8601 UTC |
| `status` | TEXT (enum) | NOT NULL, default `active` | `active` \| `error` \| `syncing` |
| `error_message` | TEXT | nullable | Set when status is `error` |

**Uniqueness rule**: `path` must be unique across all sources. Registering a duplicate path returns a 409 Conflict.

**State transitions**:
```
[registration] → active
active → syncing  (poll/refresh triggered)
syncing → active  (poll succeeded)
syncing → error   (unreachable, manifest missing, etc.)
error → syncing   (manual refresh or next poll)
[deletion]    → (removed)
```

---

## Virtual / Computed Entities

These are not persisted in SQLite but computed at request time and transmitted over the API.

### FileEntry

Represents a single file or directory node within a source's tree.

| Field | Type | Notes |
|-------|------|-------|
| `path` | string | Relative path from source root (e.g., `docs/guide/intro.md`) |
| `name` | string | Filename or directory name (last segment of `path`) |
| `is_dir` | boolean | `true` for directories, `false` for files |
| `size` | integer \| null | File size in bytes; null if unavailable |
| `modified_at` | string \| null | ISO 8601 UTC; null if unavailable |
| `source_id` | UUID | Parent source reference |

### DirectoryTree

Hierarchical structure returned by `GET /api/v1/sources/{id}/tree`.

```json
{
  "source_id": "uuid",
  "root": {
    "path": "",
    "name": "<source name>",
    "is_dir": true,
    "children": [
      {
        "path": "docs",
        "name": "docs",
        "is_dir": true,
        "children": [
          {
            "path": "docs/intro.md",
            "name": "intro.md",
            "is_dir": false,
            "size": 1234,
            "modified_at": "2026-06-30T00:00:00Z"
          }
        ]
      }
    ]
  }
}
```

---

## External Convention: index.json Manifest

Used by `http` and `localhost` source types. The backend fetches `{base_url}/index.json`.

```json
{
  "version": "1",
  "files": [
    { "path": "guide/intro.md", "size": 1234, "modified": "2026-06-30T00:00:00Z" },
    { "path": "api/reference.md", "size": 5678, "modified": "2026-06-29T10:00:00Z" }
  ]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `version` | string | yes | Must be `"1"` for v1 |
| `files` | array | yes | List of file descriptors |
| `files[].path` | string | yes | Relative to base URL (no leading `/`) |
| `files[].size` | integer | no | Bytes; omit if unknown |
| `files[].modified` | string | no | ISO 8601; omit if unknown |

**Error behavior**: If `index.json` is absent or malformed, source status → `error` with descriptive `error_message`.

---

## SSE Event Payload

Pushed to connected clients when local filesystem changes are detected.

```json
{
  "event": "file_created",
  "source_id": "uuid",
  "path": "docs/new-file.md"
}
```

| Field | Values |
|-------|--------|
| `event` | `file_created` \| `file_deleted` \| `file_modified` \| `file_renamed` |
| `source_id` | UUID of the affected source |
| `path` | Relative path of the changed file |
| `old_path` | Previous path (only present for `file_renamed`) |
