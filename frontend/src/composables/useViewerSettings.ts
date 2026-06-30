import { ref } from 'vue'

const fontSize = ref(localStorage.getItem('ds-font-size') ?? 'base')

export function useViewerSettings() {
  function setFontSize(size: string) {
    fontSize.value = size
    localStorage.setItem('ds-font-size', size)
  }
  return { fontSize, setFontSize }
}
