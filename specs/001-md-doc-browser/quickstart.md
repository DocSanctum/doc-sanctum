# Quickstart Validation Guide: MD Document Browser

**Feature**: 001-md-doc-browser
**Date**: 2026-06-30

이 가이드는 서비스가 올바르게 동작하는지 end-to-end로 검증하는 시나리오를 담고 있습니다.
구현 코드는 포함하지 않으며, 실행 방법과 기대 결과만 다룹니다.

---

## Prerequisites

- Docker 및 Docker Compose 설치
- 테스트용 MD 파일이 있는 로컬 폴더 (예: `~/test-docs/`)
- 인터넷 연결 (GitHub URL 테스트용)

---

## Setup

```bash
# 1. 저장소 클론 후 프로젝트 루트로 이동
cd doc-sanctum

# 2. 로컬 문서 폴더를 환경변수로 지정 (docker-compose.override.yml 또는 .env)
echo "LOCAL_DOCS_PATH=$HOME/test-docs" > .env

# 3. 전체 스택 기동
docker compose up --build

# 서비스 확인
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000/api/v1
# - API Docs: http://localhost:8000/docs
```

---

## Validation Scenario 1 — 로컬 폴더 등록 및 파일 탐색 (US1, P1)

### 준비
```bash
mkdir -p ~/test-docs/guide ~/test-docs/api
echo "# Hello" > ~/test-docs/README.md
echo "# Guide" > ~/test-docs/guide/intro.md
echo "# API Reference" > ~/test-docs/api/reference.md
```

### 실행
1. 브라우저에서 `http://localhost:3000` 접속
2. "Add Source" 클릭 → Type: `local`, Path: `/host-docs` (컨테이너 내 마운트 경로), Name: `Test Docs`
3. "Register" 클릭

### 기대 결과
- 3초 이내에 좌측 사이드바에 `Test Docs` 소스가 나타남
- 하위에 `README.md`, `guide/intro.md`, `api/reference.md` 가 계층 구조로 표시됨
- `README.md` 클릭 → 우측 패널에 "Hello" 제목이 렌더링된 형태로 표시됨

### 검증 API (직접 호출)
```bash
curl http://localhost:8000/api/v1/sources
# → 등록된 source 1건 반환

curl "http://localhost:8000/api/v1/sources/{source_id}/tree"
# → 3개 파일이 포함된 DirectoryTree 반환
```

---

## Validation Scenario 2 — 실시간 파일 추가 감지 (US1, SC-003)

### 실행 (Scenario 1 완료 후)
```bash
echo "# New Doc" > ~/test-docs/new-file.md
```

### 기대 결과
- 파일 추가 후 5초 이내에 사이드바의 `Test Docs` 트리에 `new-file.md` 가 자동으로 나타남
- 브라우저 새로고침 없이 갱신되어야 함

---

## Validation Scenario 3 — GitHub 공개 저장소 등록 (US2, P2)

### 실행
1. "Add Source" 클릭 → Type: `github`, Path: `https://github.com/sindresorhus/awesome`
2. "Register" 클릭

### 기대 결과
- 사이드바에 `awesome` 소스와 함께 저장소 내 `.md` 파일 목록이 나타남
- `readme.md` 클릭 → 우측 패널에 내용 렌더링
- Source status가 `active`로 표시됨

### 검증 API
```bash
curl "http://localhost:8000/api/v1/sources/{source_id}/tree"
# → GitHub 저장소의 MD 파일 목록 반환
```

---

## Validation Scenario 4 — HTTP manifest 경로 등록 (US2)

### 준비 (로컬 파일 서버 시뮬레이션)
```bash
# 테스트용 manifest와 MD 파일 준비
mkdir -p /tmp/http-docs/guide
echo '{"version":"1","files":[{"path":"guide/hello.md"}]}' > /tmp/http-docs/index.json
echo "# Hello from HTTP" > /tmp/http-docs/guide/hello.md

# Python 간이 파일 서버 실행 (별도 터미널)
python3 -m http.server 9090 --directory /tmp/http-docs
```

### 실행
1. "Add Source" → Type: `http`, Path: `http://host.docker.internal:9090`
2. "Register" 클릭

### 기대 결과
- `guide/hello.md` 가 사이드바에 표시됨
- 클릭 시 "Hello from HTTP" 렌더링됨

---

## Validation Scenario 5 — MD 렌더링 품질 (US3, P1)

### 준비
```bash
cat > ~/test-docs/render-test.md << 'EOF'
# Heading 1

## Heading 2

**Bold** and _italic_ and ~~strikethrough~~

| Col A | Col B |
|-------|-------|
| val 1 | val 2 |

```python
def hello():
    print("syntax highlighting")
```

- [x] Task list item
- [ ] Another item

[Link to intro](guide/intro.md)
EOF
```

### 기대 결과 (파일 클릭 후)
- 모든 제목 수준 올바르게 렌더링
- 테이블이 표 형태로 표시됨
- Python 코드 블록에 문법 강조 적용
- 체크박스 목록 렌더링
- 상대 링크 클릭 시 `guide/intro.md` 가 뷰어 내에서 열림 (페이지 이동 없음)

---

## Validation Scenario 6 — 서비스 재시작 후 영속성 확인

### 실행
```bash
docker compose down
docker compose up
```

### 기대 결과
- `http://localhost:3000` 접속 시 이전에 등록된 모든 소스가 그대로 표시됨
- 재등록 없이 파일 탐색 및 열람 가능

---

## Error Scenarios

| 상황 | 기대 동작 |
|------|-----------|
| 존재하지 않는 로컬 경로 등록 | 등록 실패 + 오류 메시지 표시 |
| `index.json` 없는 HTTP URL 등록 | Source status → `error` + "manifest not found" 안내 |
| 동일 경로 중복 등록 | 409 Conflict + 안내 메시지 |
| 원격 소스 연결 중단 후 재접속 | 다음 폴링 또는 수동 새로고침으로 상태 복구 |
