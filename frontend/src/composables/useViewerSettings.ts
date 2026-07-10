import { ref } from 'vue'
import type { PaneId } from '../types'

const fontSize = ref(localStorage.getItem('ds-font-size') ?? 'base')
const lineNumbers = ref(localStorage.getItem('ds-line-numbers') === 'true')

// Keyed by PaneId so each split pane's TOC collapses independently — same
// pattern as usePanes.ts's paneColors. Falls back to the old shared key for
// pane 1 so existing users don't lose their saved preference.
const tocCollapsed = ref<Record<PaneId, boolean>>({
  1: localStorage.getItem('ds-toc-collapsed-1') === 'true'
    || localStorage.getItem('ds-toc-collapsed') === 'true',
  2: localStorage.getItem('ds-toc-collapsed-2') === 'true',
})

export function useViewerSettings() {
  function setFontSize(size: string) {
    fontSize.value = size
    localStorage.setItem('ds-font-size', size)
  }
  function isTocCollapsed(paneId: PaneId): boolean {
    return tocCollapsed.value[paneId]
  }
  function toggleToc(paneId: PaneId) {
    const next = !tocCollapsed.value[paneId]
    tocCollapsed.value = { ...tocCollapsed.value, [paneId]: next }
    localStorage.setItem(`ds-toc-collapsed-${paneId}`, String(next))
  }
  function setLineNumbers(enabled: boolean) {
    lineNumbers.value = enabled
    localStorage.setItem('ds-line-numbers', String(enabled))
  }
  return { fontSize, setFontSize, tocCollapsed, isTocCollapsed, toggleToc, lineNumbers, setLineNumbers }
}
