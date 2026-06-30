# API Contracts: MD Document Browser

**Feature**: 001-md-doc-browser
**Base URL**: `http://localhost:8000/api/v1`
**Date**: 2026-06-30

All requests and responses use `application/json` unless noted.

---

## Sources

### Register a Source Path

```
POST /api/v1/sources
```

**Request body**:
```json
{
  "name": "My Docs",
  "type": "local",
  "path": "/Users/alice/documents/notes",
  "polling_interval_seconds": null
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | no | Defaults to last path segment |
| `type` | yes | `local` \| `github` \| `http` \| `localhost` |
| `path` | yes | Filesystem path or base URL |
| `polling_interval_seconds` | no | Remote only. Default: github=600, http/localhost=300 |

**Responses**:

| Status | Meaning |
|--------|---------|
| 201 Created | Source registered; returns `Source` object |
| 409 Conflict | Path already registered |
| 422 Unprocessable | Validation error (e.g., invalid type) |

---

### List All Sources

```
GET /api/v1/sources
```

**Response 200**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Docs",
    "type": "local",
    "path": "/Users/alice/documents/notes",
    "polling_interval_seconds": null,
    "created_at": "2026-06-30T10:00:00Z",
    "status": "active",
    "error_message": null
  }
]
```

---

### Delete a Source

```
DELETE /api/v1/sources/{source_id}
```

**Responses**:

| Status | Meaning |
|--------|---------|
| 204 No Content | Successfully removed |
| 404 Not Found | Source does not exist |

---

### Update Source Settings

```
PATCH /api/v1/sources/{source_id}
```

**Request body** (all fields optional):
```json
{
  "name": "Renamed Docs",
  "polling_interval_seconds": 120
}
```

**Responses**:

| Status | Meaning |
|--------|---------|
| 200 OK | Updated; returns updated `Source` object |
| 404 Not Found | Source does not exist |

---

## File Tree & Content

### Get File Tree

```
GET /api/v1/sources/{source_id}/tree
```

Returns the recursive `DirectoryTree` for the source. See data-model.md for shape.

**Responses**:

| Status | Meaning |
|--------|---------|
| 200 OK | Returns `DirectoryTree` object |
| 404 Not Found | Source does not exist |
| 503 Service Unavailable | Source is in `error` status; `error_message` included |

---

### Get File Content

```
GET /api/v1/sources/{source_id}/file?path={relative_path}
```

**Query parameters**:

| Param | Required | Notes |
|-------|----------|-------|
| `path` | yes | Relative path within source (e.g., `docs/intro.md`) |

**Response 200** — `Content-Type: text/plain; charset=utf-8`:

Raw Markdown text. The frontend is responsible for rendering.

**Responses**:

| Status | Meaning |
|--------|---------|
| 200 OK | Raw Markdown content as plain text |
| 404 Not Found | Source or file does not exist |
| 403 Forbidden | Path traversal attempt detected |

---

### Manually Refresh a Remote Source

```
POST /api/v1/sources/{source_id}/refresh
```

Triggers an immediate re-fetch of the file tree (remote sources only).
For local sources, returns 400.

**Responses**:

| Status | Meaning |
|--------|---------|
| 202 Accepted | Refresh queued; source status → `syncing` |
| 400 Bad Request | Source is of type `local` (no refresh needed) |
| 404 Not Found | Source does not exist |

---

## Real-time Events (SSE)

### Subscribe to File Change Events

```
GET /api/v1/sse/sources/{source_id}
Content-Type: text/event-stream
```

Establishes a persistent SSE connection. The server pushes events when the
source's file tree changes.

**Event format**:
```
event: file_created
data: {"source_id": "uuid", "path": "docs/new.md"}

event: file_deleted
data: {"source_id": "uuid", "path": "docs/old.md"}

event: file_modified
data: {"source_id": "uuid", "path": "docs/updated.md"}

event: file_renamed
data: {"source_id": "uuid", "path": "docs/new-name.md", "old_path": "docs/old-name.md"}

event: tree_refreshed
data: {"source_id": "uuid"}
```

`tree_refreshed` is emitted after a remote source poll completes (success or failure).

**Client behavior**: On receiving any event, the frontend re-fetches the tree for that source and updates the sidebar.

---

## Error Response Shape

All error responses use a consistent shape:

```json
{
  "detail": "Human-readable error description"
}
```
