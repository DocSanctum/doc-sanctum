import { ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../services/api'
import type { SearchMatch, SearchWarning } from '../types'

// macOS는 ⌘K, Windows/Linux는 Ctrl+K — 검색 버튼 툴팁과 팔레트 안내 문구에서
// 공통으로 쓴다(App.vue, CommandPalette.vue). 플랫폼은 세션 중 바뀌지 않으므로
// 모듈 로드 시 한 번만 계산한다.
const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
export const searchShortcutLabel = isMac ? '⌘K' : 'Ctrl+K'

// 모듈 스코프 싱글턴 상태 — usePanes.ts/useTreeReveal.ts와 동일한 패턴.
// 검색 열기 버튼(App.vue)과 팔레트 본체(CommandPalette.vue)가 서로 다른
// 컴포넌트 트리이므로 검색 세션 상태(data-model.md SearchSession)를 전역
// 공유 상태로 둔다.
const isOpen = ref(false)
const query = ref('')
const results = ref<SearchMatch[]>([])
const warnings = ref<SearchWarning[]>([])
const loading = ref(false)
const activeIndex = ref(0)

// 응답이 늦게 도착한 이전 요청이 최신 입력 결과를 덮어쓰지 않도록 토큰으로 구분한다.
let requestToken = 0

async function runSearch(q: string) {
  const trimmed = q.trim()
  // FR-013: 검색어가 비어있거나 공백뿐이면 요청 자체를 보내지 않는다.
  if (!trimmed) {
    requestToken++
    results.value = []
    warnings.value = []
    loading.value = false
    return
  }
  const token = ++requestToken
  loading.value = true
  try {
    const res = await api.search(trimmed)
    if (token !== requestToken) return
    results.value = res.matches
    warnings.value = res.warnings
  } catch {
    if (token !== requestToken) return
    results.value = []
    warnings.value = []
  } finally {
    if (token === requestToken) loading.value = false
  }
}

const debouncedRunSearch = useDebounceFn(runSearch, 250)

export function useSearch() {
  function setQuery(value: string) {
    query.value = value
    activeIndex.value = 0
    debouncedRunSearch(value)
  }

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    query.value = ''
    results.value = []
    warnings.value = []
    activeIndex.value = 0
    requestToken++
  }

  return { isOpen, query, results, warnings, loading, activeIndex, setQuery, open, close }
}
