import { useUrlSearchParams } from '@vueuse/core'

interface ViewerUrlParams {
  source?: string
  file?: string
  source2?: string
  file2?: string
  activePane?: string
}

const params = useUrlSearchParams<ViewerUrlParams>('history')

/**
 * source/file(패널 1)과 source2/file2(패널 2)는 쿼리 파라미터로, 헤딩은
 * 해시로 동기화한다. 패널 2는 분할 보기가 켜져 있을 때만 쿼리에 존재하며,
 * 기존 단일 패널 링크(source/file만 있는 URL)와 하위 호환된다
 * (contracts/pane-url-scheme.md 참조). 헤딩 해시는 활성 패널 기준 단일
 * 값만 유지한다. 두 경로 모두 history.replaceState만 사용해 스크롤/탐색마다
 * 브라우저 히스토리 스택이 쌓이지 않도록 한다.
 */
export function useViewerUrl() {
  function getSourceId(): string | null {
    return params.source || null
  }

  function getFilePath(): string | null {
    return params.file || null
  }

  function setLocation(sourceId: string | null, filePath: string | null) {
    params.source = sourceId ?? undefined
    params.file = filePath ?? undefined
  }

  function getSourceId2(): string | null {
    return params.source2 || null
  }

  function getFilePath2(): string | null {
    return params.file2 || null
  }

  function setLocation2(sourceId: string | null, filePath: string | null) {
    params.source2 = sourceId ?? undefined
    params.file2 = filePath ?? undefined
  }

  function getActivePane(): 1 | 2 {
    return params.activePane === '2' ? 2 : 1
  }

  function setActivePane(paneId: 1 | 2) {
    params.activePane = paneId === 2 ? '2' : undefined
  }

  function getHeadingId(): string | null {
    const hash = window.location.hash
    return hash ? decodeURIComponent(hash.slice(1)) : null
  }

  function setHeadingId(headingId: string | null) {
    const url = new URL(window.location.href)
    url.hash = headingId ? encodeURIComponent(headingId) : ''
    window.history.replaceState(window.history.state, '', url.toString())
  }

  function buildPermalink(sourceId: string, filePath: string, headingId: string): string {
    // 공유 링크는 항상 단일 문서 뷰로 열리도록, 현재 URL에 남아있을 수 있는
    // 패널 2/활성 패널 파라미터를 제거하고 source/file/hash만 인코딩한다.
    const url = new URL(window.location.href)
    url.searchParams.delete('source2')
    url.searchParams.delete('file2')
    url.searchParams.delete('activePane')
    url.searchParams.set('source', sourceId)
    url.searchParams.set('file', filePath)
    url.hash = encodeURIComponent(headingId)
    return url.toString()
  }

  return {
    getSourceId,
    getFilePath,
    setLocation,
    getSourceId2,
    getFilePath2,
    setLocation2,
    getActivePane,
    setActivePane,
    getHeadingId,
    setHeadingId,
    buildPermalink,
  }
}
