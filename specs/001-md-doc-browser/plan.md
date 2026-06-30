# Implementation Plan: MD Document Browser

**Branch**: `001-md-doc-browser` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-md-doc-browser/spec.md`

## Summary

로컬 폴더 및 원격 경로(GitHub 공개 저장소, HTTP/HTTPS manifest, localhost URL)에서 MD 파일을 탐색·렌더링하는 풀스택 웹 서비스. 백엔드는 Python/FastAPI, 프론트엔드는 React/TypeScript/Vite, 배포는 Docker Compose. 로컬 파일 변경은 watchdog + SSE로 실시간 감지, 원격은 주기적 폴링 + 수동 새로고침. 소스 등록 정보는 SQLite에 영속 저장.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5 / Node 20 (frontend)

**Primary Dependencies**:
- Backend: FastAPI, uvicorn, watchdog, aiosqlite, SQLAlchemy Core (async), httpx
- Frontend: Vue 3, Vite 5, markdown-it, markdown-it-task-lists, highlight.js, DOMPurify, TailwindCSS, @vueuse/core, TanStack Query (Vue)

**Storage**: SQLite (via aiosqlite) — single file in named Docker volume

**Testing**: pytest + httpx (backend); Vitest + Vue Test Utils (frontend)

**Target Platform**: Docker Compose (Linux containers); dev on macOS/Linux/Windows

**Project Type**: Full-stack web service (backend API + frontend SPA)

**Performance Goals**:
- Local folder tree (1000 files) loads in < 3s (SC-001)
- File content renders in < 2s after click (SC-002)
- Local file change detected and pushed within 5s (SC-003)

**Constraints**:
- GitHub unauthenticated API: 60 req/hr → default poll interval 10 min
- Local docs must be bind-mounted into the backend container for watchdog to work
- `.claude/` and `.specify/` excluded from git (constitution V)

**Scale/Scope**: Single-user local/team tool; no auth in v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Korean Communication** — Claude가 한국어로 응답 중
- [x] **II. English Commits** — 커밋 제목 및 본문은 영어로 작성
- [x] **III. PR Upload** — 개발 완료 후 PR 생성 및 업로드 예정
- [x] **IV. Amend Policy** — 미머지 PR의 작은 수정은 `git commit --amend` 사용
- [x] **V. Git Exclusion** — `.gitignore`에 `.claude/` 및 `.specify/` 포함 확인됨

## Project Structure

### Documentation (this feature)

```text
specs/001-md-doc-browser/
├── plan.md              # 이 파일 (/speckit-plan 출력)
├── research.md          # Phase 0 출력
├── data-model.md        # Phase 1 출력
├── quickstart.md        # Phase 1 출력
├── contracts/
│   └── api.md           # REST + SSE API 계약
└── tasks.md             # Phase 2 출력 (/speckit-tasks 명령 — 별도 생성)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── sources.py       # /api/v1/sources CRUD
│   │   ├── files.py         # /api/v1/sources/{id}/tree, file
│   │   └── sse.py           # /api/v1/sse/sources/{id}
│   ├── models/
│   │   └── source.py        # SQLAlchemy Source model
│   ├── services/
│   │   ├── watcher.py       # watchdog 파일 감시 서비스
│   │   ├── github.py        # GitHub API 클라이언트
│   │   ├── manifest.py      # HTTP/HTTPS/localhost index.json 페치
│   │   └── tree_builder.py  # DirectoryTree 구성 로직
│   └── core/
│       ├── config.py        # 환경변수 설정
│       └── database.py      # aiosqlite + SQLAlchemy 설정
├── tests/
│   ├── test_sources_api.py
│   ├── test_tree_builder.py
│   └── test_watcher.py
├── Dockerfile
└── requirements.txt

frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar/
│   │   │   ├── SourceList.vue     # 등록된 소스 목록
│   │   │   ├── FileTree.vue       # 재귀 파일 트리
│   │   │   └── AddSourceModal.vue # 소스 등록 폼
│   │   └── Viewer/
│   │       ├── MarkdownViewer.vue # markdown-it 렌더러
│   │       └── EmptyState.vue     # 파일 미선택 상태
│   ├── composables/
│   │   ├── useSources.ts      # TanStack Query: 소스 CRUD
│   │   ├── useFileTree.ts     # TanStack Query: 트리 조회
│   │   └── useSSE.ts          # @vueuse/core EventSource 연결 관리
│   ├── services/
│   │   └── api.ts             # fetch 기반 API 클라이언트
│   ├── types/
│   │   └── index.ts           # Source, FileEntry, DirectoryTree 타입
│   └── App.vue                # 루트 레이아웃 (사이드바 + 뷰어)
├── tests/
├── Dockerfile
├── nginx.conf                 # /api → backend 프록시
└── package.json

docker-compose.yml             # 프로덕션 구성
docker-compose.override.yml    # 개발 오버라이드 (볼륨 마운트, HMR)
.env.example                   # LOCAL_DOCS_PATH 등 환경변수 예시
```

**Structure Decision**: Web application (Option 2) — `backend/`와 `frontend/` 분리. Docker Compose 최상위 레벨에 `docker-compose.yml` 배치.

## Complexity Tracking

> **Constitution Check 위반 없음 — 이 섹션 해당 없음**
