import { ref } from 'vue'

const fontSize = ref(localStorage.getItem('ds-font-size') ?? 'base')
const tocCollapsed = ref(localStorage.getItem('ds-toc-collapsed') === 'true')

export function useViewerSettings() {
  function setFontSize(size: string) {
    fontSize.value = size
    localStorage.setItem('ds-font-size', size)
  }
  function toggleToc() {
    tocCollapsed.value = !tocCollapsed.value
    localStorage.setItem('ds-toc-collapsed', String(tocCollapsed.value))
  }
  return { fontSize, setFontSize, tocCollapsed, toggleToc }
}
