import { ref } from 'vue'
import { useViewerUrl } from './useViewerUrl'
import type { PaneColor, PaneId, PaneMatch, ViewerPaneState } from '../types'

const MAX_PANES = 2

const PANE_COLOR: Record<PaneId, PaneColor> = { 1: 'blue', 2: 'amber' }

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

// 모듈 스코프 싱글턴 상태 — useViewerSettings.ts/useTreeReveal.ts와 동일한 패턴.
// App.vue와 ViewerPane.vue, FileTree.vue가 서로 다른 컴포넌트 트리이므로
// 패널 목록을 전역 공유 상태로 둔다(FR-003 최대 2개, FR-007 최소 1개 유지).
const panes = ref<ViewerPaneState[]>(initialPanes())
const activePaneId = ref<PaneId>(panes.value.length === 2 ? viewerUrl.getActivePane() : 1)

function syncUrl() {
  const pane1 = panes.value.find((p) => p.id === 1) ?? null
  const pane2 = panes.value.find((p) => p.id === 2) ?? null
  viewerUrl.setLocation(pane1?.sourceId ?? null, pane1?.filePath ?? null)
  viewerUrl.setLocation2(pane2?.sourceId ?? null, pane2?.filePath ?? null)
  viewerUrl.setActivePane(pane2 ? activePaneId.value : 1)
}

export function usePanes() {
  function colorOf(paneId: PaneId): PaneColor {
    return PANE_COLOR[paneId]
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

  function setPaneDocument(paneId: PaneId, sourceId: string | null, filePath: string | null) {
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
    syncUrl()
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
    syncUrl()
  }

  function closePane(paneId: PaneId) {
    if (panes.value.length <= 1) return
    const remaining = panes.value.find((p) => p.id !== paneId)
    if (!remaining) return
    panes.value = [{ id: 1, sourceId: remaining.sourceId, filePath: remaining.filePath }]
    activePaneId.value = 1
    syncUrl()
  }

  function clearSource(sourceId: string) {
    // 소스가 삭제되면, 그 소스의 문서를 표시 중이던 패널을 빈 상태로 되돌린다
    // (기존 단일 뷰어의 fetchError/EmptyState 패턴을 패널별로 재사용).
    let changed = false
    panes.value = panes.value.map((p) => {
      if (p.sourceId === sourceId) {
        changed = true
        return { ...p, sourceId: null, filePath: null }
      }
      return p
    })
    if (changed) syncUrl()
  }

  return {
    panes,
    activePaneId,
    colorOf,
    paneMatches,
    setActivePane,
    setPaneDocument,
    openInActivePane,
    canAddPane,
    addPane,
    closePane,
    clearSource,
  }
}
