import { useUrlSearchParams } from '@vueuse/core'

interface ViewerUrlParams {
  source?: string
  file?: string
}

const params = useUrlSearchParams<ViewerUrlParams>('history')

/**
 * source/file은 쿼리 파라미터로, 헤딩은 해시로 동기화한다. 두 경로 모두
 * history.replaceState만 사용해 스크롤/탐색마다 브라우저 히스토리 스택이
 * 쌓이지 않도록 한다(@vueuse/core의 useUrlSearchParams가 내부적으로 항상
 * replaceState를 사용하는 것과 동일한 방식으로 해시도 맞춘다).
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
    const url = new URL(window.location.href)
    url.searchParams.set('source', sourceId)
    url.searchParams.set('file', filePath)
    url.hash = encodeURIComponent(headingId)
    return url.toString()
  }

  return { getSourceId, getFilePath, setLocation, getHeadingId, setHeadingId, buildPermalink }
}
