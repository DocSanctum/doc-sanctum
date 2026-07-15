import { ref } from 'vue'
import { useViewerUrl } from './useViewerUrl'
import type { PaneColor, PaneId, PaneMatch, ViewerPaneState } from '../types'

const MAX_PANES = 2

const DEFAULT_PANE_COLOR: Record<PaneId, PaneColor> = { 1: 'blue', 2: 'amber' }

// 선택 가능한 패널 색상 팔레트 — 색상 원을 클릭하면 이 목록에서 고를 수 있다.
export const PANE_COLOR_OPTIONS: PaneColor[] = ['blue', 'sky', 'amber', 'orange', 'red', 'purple', 'gray']

const PANE_COLOR_CLASSES: Record<
  PaneColor,
  { border: string; bg: string; text: string; tint: string; hover: string; solidHover: string }
> = {
  blue: {
    border: 'border-blue-500 dark:border-blue-400',
    bg: 'bg-blue-500 dark:bg-blue-400',
    text: 'text-blue-500 dark:text-blue-400',
    tint: 'bg-blue-500/10 dark:bg-blue-400/10',
    hover: 'hover:bg-blue-500/15 dark:hover:bg-blue-400/20',
    solidHover: 'hover:bg-blue-600 dark:hover:bg-blue-500',
  },
  amber: {
    border: 'border-amber-500 dark:border-amber-400',
    bg: 'bg-amber-500 dark:bg-amber-400',
    text: 'text-amber-500 dark:text-amber-400',
    tint: 'bg-amber-500/10 dark:bg-amber-400/10',
    hover: 'hover:bg-amber-500/15 dark:hover:bg-amber-400/20',
    solidHover: 'hover:bg-amber-600 dark:hover:bg-amber-500',
  },
  orange: {
    border: 'border-orange-500 dark:border-orange-400',
    bg: 'bg-orange-500 dark:bg-orange-400',
    text: 'text-orange-500 dark:text-orange-400',
    tint: 'bg-orange-500/10 dark:bg-orange-400/10',
    hover: 'hover:bg-orange-500/15 dark:hover:bg-orange-400/20',
    solidHover: 'hover:bg-orange-600 dark:hover:bg-orange-500',
  },
  sky: {
    border: 'border-sky-500 dark:border-sky-400',
    bg: 'bg-sky-500 dark:bg-sky-400',
    text: 'text-sky-500 dark:text-sky-400',
    tint: 'bg-sky-500/10 dark:bg-sky-400/10',
    hover: 'hover:bg-sky-500/15 dark:hover:bg-sky-400/20',
    solidHover: 'hover:bg-sky-600 dark:hover:bg-sky-500',
  },
  red: {
    border: 'border-red-500 dark:border-red-400',
    bg: 'bg-red-500 dark:bg-red-400',
    text: 'text-red-500 dark:text-red-400',
    tint: 'bg-red-500/10 dark:bg-red-400/10',
    hover: 'hover:bg-red-500/15 dark:hover:bg-red-400/20',
    solidHover: 'hover:bg-red-600 dark:hover:bg-red-500',
  },
  purple: {
    border: 'border-purple-500 dark:border-purple-400',
    bg: 'bg-purple-500 dark:bg-purple-400',
    text: 'text-purple-500 dark:text-purple-400',
    tint: 'bg-purple-500/10 dark:bg-purple-400/10',
    hover: 'hover:bg-purple-500/15 dark:hover:bg-purple-400/20',
    solidHover: 'hover:bg-purple-600 dark:hover:bg-purple-500',
  },
  gray: {
    border: 'border-gray-500 dark:border-gray-400',
    bg: 'bg-gray-500 dark:bg-gray-400',
    text: 'text-gray-500 dark:text-gray-400',
    tint: 'bg-gray-500/10 dark:bg-gray-400/10',
    hover: 'hover:bg-gray-500/15 dark:hover:bg-gray-400/20',
    solidHover: 'hover:bg-gray-600 dark:hover:bg-gray-500',
  },
}

export function paneColorClass(color: PaneColor, kind: 'border' | 'bg' | 'text' | 'tint' | 'hover' | 'solidHover'): string {
  return PANE_COLOR_CLASSES[color][kind]
}

const viewerUrl = useViewerUrl()

function initialPanes(): ViewerPaneState[] {
  const panes: ViewerPaneState[] = [
    { id: 1, sourceId: viewerUrl.getSourceId(), filePath: viewerUrl.getFilePath() },
  ]
  const sourceId2 = viewerUrl.getSourceId2()
  const filePath2 = viewerUrl.getFilePath2()
  if (sourceId2 && filePath2) {
    panes.push({ id: 2, sourceId: sourceId2, filePath: filePath2 })
  }
  return panes
}

interface HistoryEntry {
  sourceId: string
  filePath: string
}

// Per-pane visit history (browser back/forward style) — tracks documents opened
// in a pane via clicks/search/links, independent of the file tree's own order.
function initialHistory(initPanes: ViewerPaneState[]): { history: Record<PaneId, HistoryEntry[]>; index: Record<PaneId, number> } {
  const history: Record<PaneId, HistoryEntry[]> = { 1: [], 2: [] }
  const index: Record<PaneId, number> = { 1: -1, 2: -1 }
  for (const p of initPanes) {
    if (p.sourceId && p.filePath) {
      history[p.id] = [{ sourceId: p.sourceId, filePath: p.filePath }]
      index[p.id] = 0
    }
  }
  return { history, index }
}

// 모듈 스코프 싱글턴 상태 — useViewerSettings.ts/useTreeReveal.ts와 동일한 패턴.
// App.vue와 ViewerPane.vue, FileTree.vue가 서로 다른 컴포넌트 트리이므로
// 패널 목록을 전역 공유 상태로 둔다(FR-003 최대 2개, FR-007 최소 1개 유지).
const panes = ref<ViewerPaneState[]>(initialPanes())
const activePaneId = ref<PaneId>(panes.value.length === 2 ? viewerUrl.getActivePane() : 1)
const { history: initHistory, index: initHistoryIndex } = initialHistory(panes.value)
const paneHistory = ref<Record<PaneId, HistoryEntry[]>>(initHistory)
const paneHistoryIndex = ref<Record<PaneId, number>>(initHistoryIndex)
// 패널 색상 원을 클릭해 사용자가 직접 바꿀 수 있다 — id별 기본값(파랑/노랑)에서
// 시작하되, 분할을 닫아 패널 1개로 돌아가면 다음에 다시 열 때 헷갈리지 않도록
// 기본값으로 리셋한다(closePane 참고).
const paneColors = ref<Record<PaneId, PaneColor>>({ ...DEFAULT_PANE_COLOR })

function syncUrl() {
  const pane1 = panes.value.find((p) => p.id === 1) ?? null
  const pane2 = panes.value.find((p) => p.id === 2) ?? null
  viewerUrl.setLocation(pane1?.sourceId ?? null, pane1?.filePath ?? null)
  viewerUrl.setLocation2(pane2?.sourceId ?? null, pane2?.filePath ?? null)
  viewerUrl.setActivePane(pane2 ? activePaneId.value : 1)
}

export function usePanes() {
  function colorOf(paneId: PaneId): PaneColor {
    return paneColors.value[paneId]
  }

  function setPaneColor(paneId: PaneId, color: PaneColor) {
    if (!panes.value.some((p) => p.id === paneId)) return
    paneColors.value = { ...paneColors.value, [paneId]: color }
  }

  function paneMatches(sourceId: string, filePath: string): PaneMatch[] {
    return panes.value
      .filter((p) => p.sourceId === sourceId && p.filePath === filePath)
      .map((p) => ({ paneId: p.id, color: colorOf(p.id) }))
  }

  function setActivePane(paneId: PaneId) {
    if (!panes.value.some((p) => p.id === paneId) || activePaneId.value === paneId) return
    activePaneId.value = paneId
    syncUrl()
  }

  // pushHistory=false is used by goBack/goForward so replaying a history
  // entry doesn't itself get recorded as a new visit.
  function setPaneDocument(paneId: PaneId, sourceId: string | null, filePath: string | null, pushHistory = true) {
    const pane = panes.value.find((p) => p.id === paneId)
    if (!pane) return
    pane.sourceId = sourceId
    pane.filePath = filePath
    // 헤딩 해시는 활성 패널 기준 단일 값이다 — 활성 패널의 문서가 바뀌면
    // 이전 문서의 헤딩을 가리키던 해시를 지운다(기존 004의 setSelectedFile
    // 동작과 동일). 초기 로드 복원(initialPanes)은 이 함수를 거치지 않으므로
    // 퍼머링크로 들어온 해시는 그대로 유지된다.
    if (paneId === activePaneId.value) {
      viewerUrl.setHeadingId(null)
    }
    if (pushHistory) {
      if (sourceId && filePath) {
        recordVisit(paneId, sourceId, filePath)
      } else {
        // Explicitly clearing a pane's document also clears its history —
        // there's nothing left to go back/forward to.
        paneHistory.value = { ...paneHistory.value, [paneId]: [] }
        paneHistoryIndex.value = { ...paneHistoryIndex.value, [paneId]: -1 }
      }
    }
    syncUrl()
  }

  // Appends a visit to the pane's history stack, discarding any forward
  // entries past the current position (standard browser back/forward semantics).
  function recordVisit(paneId: PaneId, sourceId: string, filePath: string) {
    const stack = paneHistory.value[paneId]
    const idx = paneHistoryIndex.value[paneId]
    const current = stack[idx]
    if (current && current.sourceId === sourceId && current.filePath === filePath) return
    const truncated = [...stack.slice(0, idx + 1), { sourceId, filePath }]
    paneHistory.value = { ...paneHistory.value, [paneId]: truncated }
    paneHistoryIndex.value = { ...paneHistoryIndex.value, [paneId]: truncated.length - 1 }
  }

  function canGoBack(paneId: PaneId): boolean {
    return paneHistoryIndex.value[paneId] > 0
  }

  function canGoForward(paneId: PaneId): boolean {
    const idx = paneHistoryIndex.value[paneId]
    return idx >= 0 && idx < paneHistory.value[paneId].length - 1
  }

  function goBack(paneId: PaneId) {
    if (!canGoBack(paneId)) return
    const newIdx = paneHistoryIndex.value[paneId] - 1
    paneHistoryIndex.value = { ...paneHistoryIndex.value, [paneId]: newIdx }
    const entry = paneHistory.value[paneId][newIdx]
    setPaneDocument(paneId, entry.sourceId, entry.filePath, false)
  }

  function goForward(paneId: PaneId) {
    if (!canGoForward(paneId)) return
    const newIdx = paneHistoryIndex.value[paneId] + 1
    paneHistoryIndex.value = { ...paneHistoryIndex.value, [paneId]: newIdx }
    const entry = paneHistory.value[paneId][newIdx]
    setPaneDocument(paneId, entry.sourceId, entry.filePath, false)
  }

  function openInActivePane(sourceId: string, filePath: string) {
    setPaneDocument(activePaneId.value, sourceId, filePath)
  }

  function canAddPane(): boolean {
    return panes.value.length < MAX_PANES
  }

  function addPane() {
    if (!canAddPane()) return
    panes.value.push({ id: 2, sourceId: null, filePath: null })
    activePaneId.value = 2
    paneHistory.value = { ...paneHistory.value, 2: [] }
    paneHistoryIndex.value = { ...paneHistoryIndex.value, 2: -1 }
    syncUrl()
  }

  function closePane(paneId: PaneId) {
    if (panes.value.length <= 1) return
    const remaining = panes.value.find((p) => p.id !== paneId)
    if (!remaining) return
    // The surviving pane keeps its history, now under slot 1; the closed
    // pane's history (slot 2) is dropped.
    const remainingHistory = paneHistory.value[remaining.id]
    const remainingIndex = paneHistoryIndex.value[remaining.id]
    panes.value = [{ id: 1, sourceId: remaining.sourceId, filePath: remaining.filePath }]
    activePaneId.value = 1
    paneColors.value = { ...DEFAULT_PANE_COLOR }
    paneHistory.value = { 1: remainingHistory, 2: [] }
    paneHistoryIndex.value = { 1: remainingIndex, 2: -1 }
    syncUrl()
  }

  function clearSource(sourceId: string) {
    // 소스가 삭제되면, 그 소스의 문서를 표시 중이던 패널을 빈 상태로 되돌린다
    // (기존 단일 뷰어의 fetchError/EmptyState 패턴을 패널별로 재사용).
    const clearedPaneIds: PaneId[] = []
    panes.value = panes.value.map((p) => {
      if (p.sourceId === sourceId) {
        clearedPaneIds.push(p.id)
        return { ...p, sourceId: null, filePath: null }
      }
      return p
    })
    if (clearedPaneIds.length > 0) {
      // The deleted source's history entries no longer resolve to anything,
      // so drop that pane's whole stack rather than leave dangling entries.
      const newHistory = { ...paneHistory.value }
      const newIndex = { ...paneHistoryIndex.value }
      for (const id of clearedPaneIds) {
        newHistory[id] = []
        newIndex[id] = -1
      }
      paneHistory.value = newHistory
      paneHistoryIndex.value = newIndex
      syncUrl()
    }
  }

  return {
    panes,
    activePaneId,
    colorOf,
    setPaneColor,
    paneMatches,
    setActivePane,
    setPaneDocument,
    openInActivePane,
    canAddPane,
    addPane,
    closePane,
    clearSource,
    canGoBack,
    canGoForward,
    goBack,
    goForward,
  }
}
