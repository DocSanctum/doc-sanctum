import { ref } from 'vue'

type Theme = 'dark' | 'light'

const theme = ref<Theme>((localStorage.getItem('ds-theme') as Theme) ?? 'dark')

function applyTheme(t: Theme) {
  theme.value = t
  localStorage.setItem('ds-theme', t)
  document.documentElement.classList.toggle('dark', t === 'dark')
}

applyTheme(theme.value)

export function useTheme() {
  return { theme, applyTheme }
}
