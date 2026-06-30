---
description: "Task list for MD Document Browser implementation"
---

# Tasks: MD Document Browser

**Input**: Design documents from `specs/001-md-doc-browser/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅

**Tests**: 테스트 태스크는 spec에 명시되지 않아 포함하지 않음. 필요 시 별도 추가 가능.

**Organization**: User Story 기준으로 페이즈 구분 — 각 스토리를 독립적으로 구현·검증 가능.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 의존성 없음)
- **[Story]**: 해당 태스크가 속하는 User Story (US1, US2, US3)
- 모든 태스크에 정확한 파일 경로 포함

---

## Phase 1: Setup (공통 프로젝트 초기화)

**Purpose**: 백엔드·프론트엔드·Docker 기본 구조 생성

- [x] T001 Create backend/ directory structure: `backend/app/api/`, `backend/app/models/`, `backend/app/services/`, `backend/app/core/`, `backend/tests/`
- [x] T002 [P] Create frontend/ directory structure: `frontend/src/components/Sidebar/`, `frontend/src/components/Viewer/`, `frontend/src/composables/`, `frontend/src/services/`, `frontend/src/types/`
- [x] T003 Create `docker-compose.yml` with `backend` service (FastAPI/uvicorn), `frontend` service (Nginx), and `sqlite_data` named volume
- [x] T004 [P] Create `docker-compose.override.yml` for local development (volume bind mounts for local doc paths, Vite HMR port)
- [x] T005 [P] Create `.env.example` with `LOCAL_DOCS_PATH`, `BACKEND_PORT=8000`, `FRONTEND_PORT=3000`, `POLL_INTERVAL_DEFAULT=300`
- [x] T006 Initialize Python backend: create `backend/requirements.txt` (fastapi, uvicorn, watchdog, aiosqlite, sqlalchemy, httpx) and `backend/Dockerfile`
- [x] T007 [P] Initialize Vue 3 + TypeScript frontend: create `frontend/package.json` (vue, vite, typescript, markdown-it, markdown-it-task-lists, highlight.js, dompurify, @vueuse/core, @tanstack/vue-query, tailwindcss), `frontend/Dockerfile`, `frontend/vite.config.ts`

---

## Phase 2: Foundational (공통 인프라 — 모든 User Story 차단)

**Purpose**: DB, 설정, 공유 타입, FastAPI 앱 뼈대 — 완료 전까지 User Story 구현 불가

**⚠️ CRITICAL**: 이 페이즈 완료 전까지 Phase 3+ 작업 시작 불가

- [x] T008 Create `backend/app/core/config.py` with pydantic-settings `Settings` class loading env vars (`DATABASE_URL`, `HOST_DOCS_ROOT`, `DEFAULT_POLL_INTERVAL`)
- [x] T009 Create `backend/app/core/database.py` with aiosqlite engine, SQLAlchemy async session factory, and `create_tables()` startup function
- [x] T010 [P] Create `backend/app/models/source.py` with SQLAlchemy `Source` table: `id` (UUID PK), `name`, `type` (local/github/http/localhost), `path` (UNIQUE), `polling_interval_seconds`, `created_at`, `status` (active/error/syncing), `error_message`
- [x] T011 [P] Create `backend/app/main.py` with FastAPI app init, CORS middleware (allow frontend origin), lifespan handler calling `create_tables()`, and router includes for sources, files, sse
- [x] T012 Create `frontend/src/types/index.ts` with TypeScript interfaces: `Source`, `FileEntry`, `DirectoryTree`, `SSEEvent`
- [x] T013 [P] Create `frontend/src/services/api.ts` with base fetch wrapper and methods: `getSources()`, `registerSource()`, `deleteSource()`, `patchSource()`, `getTree()`, `getFileContent()`, `refreshSource()`
- [x] T014 [P] Create `frontend/nginx.conf` proxying `/api` and `/sse` to `http://backend:8000`, serving built Vue app at `/`

**Checkpoint**: 인프라 준비 완료 — User Story 구현 시작 가능

---

## Phase 3: User Story 1 — 로컬 폴더 등록 및 파일 탐색 (Priority: P1) 🎯 MVP

**Goal**: 로컬 폴더를 등록하고, MD 파일 계층 목록을 사이드바에서 탐색하며, 실시간 파일 추가/삭제를 감지한다.

**Independent Test**: 로컬 폴더 등록 → 사이드바에 파일 트리 표시 → 새 파일 추가 시 5초 내 자동 갱신 (quickstart Scenario 1, 2)

### Implementation for User Story 1

- [x] T015 [P] [US1] Create `backend/app/services/tree_builder.py` with `build_local_tree(source: Source) -> DirectoryTree` scanning a directory recursively for `.md` files
- [x] T016 [P] [US1] Create `backend/app/api/sources.py` with endpoints: `POST /api/v1/sources` (register, 409 on duplicate path), `GET /api/v1/sources` (list), `DELETE /api/v1/sources/{id}`, `PATCH /api/v1/sources/{id}` (update name/interval)
- [x] T017 [US1] Create `backend/app/services/watcher.py` with `SourceWatcher` class using watchdog `Observer`; emits `file_created`, `file_deleted`, `file_modified`, `file_renamed` events into an asyncio queue per source
- [x] T018 [US1] Create `backend/app/api/sse.py` with `GET /api/v1/sse/sources/{id}` SSE endpoint using `StreamingResponse`; drains the source's asyncio queue and pushes events to the client
- [x] T019 [US1] Create `backend/app/api/files.py` with `GET /api/v1/sources/{id}/tree` endpoint calling `tree_builder.build_local_tree()` and returning `DirectoryTree` JSON
- [x] T020 [P] [US1] Create `frontend/src/composables/useSources.ts` with TanStack Query `useQuery` for source list and `useMutation` for register/delete/patch operations
- [x] T021 [P] [US1] Create `frontend/src/composables/useFileTree.ts` with TanStack Query `useQuery` for `GET /api/v1/sources/{id}/tree`; invalidates on SSE events
- [x] T022 [US1] Create `frontend/src/composables/useSSE.ts` using `@vueuse/core` `useEventSource`; parses SSE events and calls `queryClient.invalidateQueries(['tree', sourceId])` on file events
- [x] T023 [P] [US1] Create `frontend/src/components/Sidebar/SourceList.vue` displaying registered sources with status badge; uses `useSources`; emits `select-source` event on click
- [x] T024 [P] [US1] Create `frontend/src/components/Sidebar/FileTree.vue` recursively rendering `DirectoryTree` nodes; emits `select-file(sourceId, path)` event on `.md` file click; uses `useFileTree` and `useSSE`
- [x] T025 [US1] Create `frontend/src/components/Sidebar/AddSourceModal.vue` with form for `name`, `type` (local only for now), `path`; calls `useSources.registerSource()`; shows validation error on failure
- [x] T026 [US1] Assemble `frontend/src/App.vue` with split layout: left sidebar (`SourceList` + `FileTree` + add button opening `AddSourceModal`), right panel placeholder (`EmptyState`); tracks `selectedFile` reactive state

**Checkpoint**: User Story 1 독립 검증 가능 — 로컬 폴더 탐색 + 실시간 갱신 동작 확인

---

## Phase 4: User Story 3 — MD 렌더링 (Priority: P1)

**Goal**: 파일 클릭 시 우측 패널에 GitHub 스타일 렌더링 표시. 문법 강조, 테이블, 체크박스, 상대 링크 지원.

**Independent Test**: render-test.md 클릭 → 모든 MD 요소 렌더링 확인, 상대 링크 클릭 시 뷰어 내 이동 (quickstart Scenario 5)

### Implementation for User Story 3

- [x] T027 [US3] Add `GET /api/v1/sources/{id}/file?path={relative_path}` to `backend/app/api/files.py`; validates path (no `../` traversal), reads file from local or remote source, returns `text/plain`
- [x] T028 [P] [US3] Configure markdown-it pipeline in `frontend/src/composables/useMarkdown.ts`: `MarkdownIt({ highlight })` with `markdown-it-task-lists`, `markdown-it-anchor`, and `highlight.js` auto-detection; export `render(src: string): string`
- [x] T029 [US3] Create `frontend/src/components/Viewer/MarkdownViewer.vue`: fetches file content via `api.getFileContent()`, passes through `useMarkdown.render()`, sanitizes with `DOMPurify.sanitize()`, renders via `v-html`; shows loading spinner while fetching
- [x] T030 [P] [US3] Create `frontend/src/components/Viewer/EmptyState.vue` with "파일을 선택하세요" placeholder shown when no file is selected
- [x] T031 [US3] Update `frontend/src/App.vue` to replace viewer placeholder with `MarkdownViewer` (when file selected) or `EmptyState`; pass `selectedFile` (sourceId + path) as props; handle `select-file` event from `FileTree`
- [x] T032 [US3] Intercept relative `.md` link clicks inside `MarkdownViewer.vue` (via `@click` delegation on the rendered `div`); resolve relative path against current file's directory; emit `navigate-file` event to update `selectedFile` in `App.vue`

**Checkpoint**: User Story 1 + 3 모두 독립 동작 확인 — 사이드바 탐색 + 렌더링 완성

---

## Phase 5: User Story 2 — 원격 경로 등록 및 탐색 (Priority: P2)

**Goal**: GitHub 공개 저장소 URL, HTTP/HTTPS manifest URL, localhost URL 등록 및 파일 탐색. 자동 폴링 + 수동 새로고침.

**Independent Test**: GitHub URL 등록 → 파일 목록 표시 → HTTP manifest URL 등록 → 파일 목록 표시 → 수동 새로고침 작동 확인 (quickstart Scenario 3, 4)

### Implementation for User Story 2

- [x] T033 [P] [US2] Create `backend/app/services/github.py` for GitHub public repo API file tree fetching (unauthenticated)
- [x] T034 [P] [US2] Create `backend/app/services/manifest.py` for HTTP/HTTPS/localhost index.json fetching and tree construction
- [x] T035 [US2] Create `backend/app/services/poller.py` with async polling scheduler for per-source interval polling of remote sources
- [x] T036 [US2] Add `POST /api/v1/sources/{id}/refresh` endpoint to `backend/app/api/sources.py` for manual remote refresh
- [x] T037 [US2] Extend `backend/app/api/sse.py` to emit `tree_refreshed` SSE event after remote poll completes
- [x] T038 [US2] Update `backend/app/services/tree_builder.py` to dispatch to github.py or manifest.py based on source type
- [x] T039 [US2] Update `frontend/src/components/Sidebar/AddSourceModal.vue` to support github/http/localhost source types with polling interval field
- [x] T040 [US2] Add manual refresh button to `frontend/src/components/Sidebar/SourceList.vue` triggering POST /refresh

**Checkpoint**: 모든 User Story 독립 동작 확인 — 로컬 + 원격 경로 탐색 + 렌더링 완성

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 오류 처리, 엣지 케이스, 최종 검증

- [x] T041 [P] Add loading skeleton and error state UI to `frontend/src/components/Sidebar/FileTree.vue` (empty folder message, fetch error with retry button)
- [x] T042 [P] Add path traversal protection to `backend/app/api/files.py` file content endpoint: reject any `path` containing `../` or resolving outside source root; return 403
- [x] T043 [P] Add duplicate path 409 Conflict handling to `backend/app/api/sources.py` `POST /api/v1/sources`: catch UNIQUE constraint violation and return 409 with descriptive message; show inline error in `AddSourceModal.vue`
- [x] T044 [P] Add source status badge (active 🟢 / syncing 🔄 / error 🔴) display to `frontend/src/components/Sidebar/SourceList.vue`
- [x] T045 Run end-to-end validation against all 6 scenarios in `specs/001-md-doc-browser/quickstart.md` and confirm all pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존성 없음 — 즉시 시작 가능
- **Foundational (Phase 2)**: Setup 완료 필요 — **US1/US3/US2 모두 차단**
- **US1 (Phase 3)**: Foundational 완료 필요
- **US3 (Phase 4)**: US1 완료 필요 (파일 트리에서 파일 선택 흐름 의존)
- **US2 (Phase 5)**: Foundational 완료 필요, US1과 병렬 가능하나 US1 완료 권장
- **Polish (Phase 6)**: 원하는 User Story 완료 후 진행

### User Story Dependencies

- **US1 (P1)**: Foundational 완료 후 시작 — 다른 Story 의존 없음
- **US3 (P1)**: US1 완료 권장 (파일 선택 상태 공유) — 파일 내용 API는 독립 개발 가능
- **US2 (P2)**: Foundational 완료 후 시작 — US1 완료 시 AddSourceModal 확장이 자연스러움

### Within Each User Story

- 백엔드 서비스 → API 엔드포인트 → 프론트엔드 composable → 컴포넌트 → App.vue 통합
- T015~T019 (백엔드) 와 T020~T022 (프론트엔드 composable) 은 병렬 진행 가능
- 컴포넌트(T023~T025)는 composable 완료 후 작업

### Parallel Opportunities

- Phase 1: T001~T007 전체 병렬 가능
- Phase 2: T008~T009 순차, T010~T014 병렬 가능
- Phase 3: T015~T016, T020~T021 백엔드/프론트엔드 팀 분리 시 병렬 가능
- Phase 5: T033~T034 (github.py / manifest.py) 완전 병렬

---

## Notes

- `[P]` 태스크는 다른 파일을 다루며 의존성 없음 — 병렬 실행 가능
- `[Story]` 레이블은 각 태스크가 어느 User Story에 속하는지 추적용
- 각 User Story는 해당 Checkpoint에서 독립적으로 검증 가능
- 커밋은 각 태스크 또는 논리적 그룹 완료 후 생성 (constitution II 준수: 영어로)
- 미머지 PR에 수정 발생 시 `git commit --amend` 사용 (constitution IV)
