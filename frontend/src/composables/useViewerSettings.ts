import { ref } from 'vue'

const fontSize = ref(localStorage.getItem('ds-font-size') ?? 'base')
const tocCollapsed = ref(localStorage.getItem('ds-toc-collapsed') === 'true')
const lineNumbers = ref(localStorage.getItem('ds-line-numbers') === 'true')

export function useViewerSettings() {
  function setFontSize(size: string) {
    fontSize.value = size
    localStorage.setItem('ds-font-size', size)
  }
  function toggleToc() {
    tocCollapsed.value = !tocCollapsed.value
    localStorage.setItem('ds-toc-collapsed', String(tocCollapsed.value))
  }
  function setLineNumbers(enabled: boolean) {
    lineNumbers.value = enabled
    localStorage.setItem('ds-line-numbers', String(enabled))
  }
  return { fontSize, setFontSize, tocCollapsed, toggleToc, lineNumbers, setLineNumbers }
}
