import githubDarkCss from 'highlight.js/styles/github-dark.css?inline'
import atomOneDarkCss from 'highlight.js/styles/atom-one-dark.css?inline'
import monokaiCss from 'highlight.js/styles/monokai.css?inline'
import tokyoNightCss from 'highlight.js/styles/tokyo-night-dark.css?inline'

const themes: Record<string, string> = {
  'github-dark': githubDarkCss,
  'atom-one-dark': atomOneDarkCss,
  'monokai': monokaiCss,
  'tokyo-night-dark': tokyoNightCss,
}

export const THEME_OPTIONS = [
  { value: 'github-dark', label: 'GitHub Dark' },
  { value: 'atom-one-dark', label: 'Atom One Dark' },
  { value: 'monokai', label: 'Monokai' },
  { value: 'tokyo-night-dark', label: 'Tokyo Night' },
]

function getStyleEl(): HTMLStyleElement {
  let el = document.getElementById('hljs-theme') as HTMLStyleElement | null
  if (!el) {
    el = document.createElement('style')
    el.id = 'hljs-theme'
    document.head.appendChild(el)
  }
  return el
}

export function applyCodeTheme(theme: string) {
  getStyleEl().textContent = themes[theme] ?? themes['github-dark']
  localStorage.setItem('ds-code-theme', theme)
}

export function initCodeTheme() {
  applyCodeTheme(localStorage.getItem('ds-code-theme') ?? 'github-dark')
}
