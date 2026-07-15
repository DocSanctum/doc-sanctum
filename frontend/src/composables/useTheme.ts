import { ref } from 'vue'
import { initCodeTheme } from './useCodeTheme'

// 'dark-gray' and 'black' are dark-mode variants that reuse every `dark:` utility
// class in the app and only swap the underlying --ds-gray-* CSS variables (see
// style.css) to a more neutral or near-black palette than Tailwind's default,
// slightly blue-tinted gray scale.
type Theme = 'dark' | 'dark-gray' | 'black' | 'light'

const theme = ref<Theme>((localStorage.getItem('ds-theme') as Theme) ?? 'dark')

function applyTheme(t: Theme) {
  theme.value = t
  localStorage.setItem('ds-theme', t)
  const isDark = t !== 'light'
  const root = document.documentElement
  root.classList.toggle('dark', isDark)
  root.classList.toggle('theme-dark-gray', t === 'dark-gray')
  root.classList.toggle('theme-black', t === 'black')
  initCodeTheme(isDark ? 'dark' : 'light')
}

applyTheme(theme.value)

export function useTheme() {
  return { theme, applyTheme }
}
