# Research: MD Document Browser

**Feature**: 001-md-doc-browser
**Date**: 2026-06-30

---

## Decision 1: Backend Language & Framework

**Decision**: Python 3.11+ with FastAPI

**Rationale**:
- MCP Python SDK (`mcp`) is the reference implementation — JS counterpart lags significantly
- LangChain, LlamaIndex, ChromaDB, pgvector, sentence-transformers are Python-first
- FastAPI provides async REST + native SSE + WebSocket with minimal boilerplate
- Auto-generates OpenAPI docs (useful for future MCP tool surface)

**Alternatives considered**:
- Node.js/TypeScript (Express, Fastify, NestJS): Adequate for v1 but JS MCP/RAG ecosystem significantly less mature; would require language switch when adding RAG in v2

---

## Decision 2: Frontend Framework

**Decision**: Vue 3 + TypeScript + Vite

**Rationale**:
- 사용자 선호에 따라 Vue 3 선택
- Vue 3의 Composition API는 사이드바 + 메인 패널 레이아웃의 상태 관리에 자연스럽게 맞음
- Vite는 Vue 공식 빌드 도구로 HMR 및 개발 경험이 뛰어남
- `@vueuse/core`의 `useEventSource`로 SSE 연결 관리 간편화
- markdown-it + highlight.js 조합으로 GFM 렌더링 및 문법 강조 구현
- VueQuery (TanStack Query Vue 어댑터)로 API 상태 관리

**MD 렌더링 라이브러리 변경**:
- `markdown-it` + `markdown-it-anchor` + `markdown-it-task-lists` (GFM 지원)
- `highlight.js` (코드 블록 문법 강조)
- Vue 컴포넌트에서 `v-html`로 렌더링 (DOMPurify로 XSS 방어)

**Alternatives considered**:
- React 18: 생태계가 크나 사용자 선호 Vue
- Nuxt 3: SSR 불필요한 단일 사용자 도구에 과도함

---

## Decision 3: Filesystem Watching

**Decision**: `watchdog` (Python library)

**Rationale**:
- Uses OS-native backends: inotify (Linux/Docker), FSEvents (macOS), ReadDirectoryChangesW (Windows)
- Unambiguous standard for Python FS watching
- Emits granular events (created, deleted, modified, moved) which map directly to SSE event types

**Alternatives considered**:
- Polling fallback: Used only when watchdog observer fails; not the primary mechanism

---

## Decision 4: Markdown Rendering Pipeline

**Decision**: `markdown-it` + `markdown-it-task-lists` + `highlight.js` + `DOMPurify`

**Rationale**:
- `markdown-it`: 빠르고 확장성 높은 Markdown 파서. GFM 호환 플러그인 생태계 풍부
- `markdown-it-task-lists`: GitHub 스타일 체크박스 목록 지원
- `highlight.js`: 190+ 언어 문법 강조 지원
- `DOMPurify`: `v-html` 사용 시 XSS 방어를 위한 HTML 살균 처리
- `markdown-it-anchor`: 제목에 앵커 링크 자동 추가

**Alternatives considered**:
- `marked`: 더 단순하나 GFM 플러그인 생태계가 markdown-it보다 작음
- `vue-markdown-render`: 래퍼 라이브러리지만 커스터마이징이 markdown-it 직접 사용보다 제한적

---

## Decision 5: Persistent Storage

**Decision**: SQLite via `aiosqlite` + SQLAlchemy Core (async)

**Rationale**:
- Single-file database, zero extra Docker service
- Stored in a named Docker volume → survives container restarts
- Relational model needed for v2: document metadata, chunk references, embedding IDs
- `aiosqlite` is fully async-compatible with FastAPI

**Alternatives considered**:
- JSON file: Concurrency issues during writes; no query capability for v2 RAG metadata
- PostgreSQL: Separate service for a v1 single-user tool is premature

---

## Decision 6: Real-time Push Mechanism

**Decision**: SSE (Server-Sent Events) via FastAPI `StreamingResponse`

**Rationale**:
- File-change pushes are strictly unidirectional (server → client)
- Native browser `EventSource` API with auto-reconnect
- Works through Nginx reverse proxies without special header tuning
- FastAPI `StreamingResponse` makes implementation trivial

**Alternatives considered**:
- WebSocket: Right tool only when client also sends messages on the same channel; not the case here

---

## Decision 7: Docker Compose Architecture

**Decision**: Two services + one named volume

```yaml
services:
  backend:   # FastAPI + watchdog; user doc dirs mounted as read-only bind mounts
  frontend:  # Nginx serving pre-built React bundle; proxies /api and /sse to backend
volumes:
  sqlite_data:  # persists registered sources + future RAG metadata
```

Local document directories are declared as bind mounts in `docker-compose.override.yml`
or via an `.env`-driven volume list, because the backend container must access the
filesystem for `watchdog` to work.

Future additions slot in cleanly:
```yaml
  chromadb:  # v2: vector store for RAG
  # or pgvector within postgres service
```

---

## Decision 8: Remote Polling Strategy

**Decision**: Per-source configurable polling interval (default 5 min) + manual refresh button

**Rationale**:
- GitHub API: rate limit 60 req/hr unauthenticated → default 10-min interval is safe
- HTTP/localhost manifest: lightweight, 1-min default acceptable
- User can set per-source interval at registration time
- Manual refresh button provides immediate control without waiting for next poll cycle

---

## Decision 9: index.json Manifest Format

**Decision**: Simple JSON structure at the root URL of any HTTP/HTTPS/localhost source

```json
{
  "version": "1",
  "files": [
    { "path": "guide/intro.md", "size": 1234, "modified": "2026-06-30T00:00:00Z" },
    { "path": "api/reference.md", "size": 5678, "modified": "2026-06-30T00:00:00Z" }
  ]
}
```

- `path`: relative to the registered base URL
- `size` and `modified`: optional metadata
- Backend fetches `{base_url}/index.json` to build the file tree

---

## All NEEDS CLARIFICATION resolved

| Item | Resolution |
|------|-----------|
| Backend language/framework | Python 3.11 + FastAPI |
| Frontend framework | Vue 3 + TypeScript + Vite |
| FS watching library | watchdog |
| MD rendering | markdown-it + markdown-it-task-lists + highlight.js + DOMPurify |
| Storage | SQLite via aiosqlite |
| Real-time mechanism | SSE (Server-Sent Events) |
| Docker Compose layout | backend + frontend + sqlite_data volume |
| Remote polling | Per-source interval (default 5 min) + manual refresh |
| HTTP/HTTPS file listing | index.json manifest convention |
