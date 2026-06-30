import githubDarkCss from 'highlight.js/styles/github-dark.css?inline'
import atomOneDarkCss from 'highlight.js/styles/atom-one-dark.css?inline'
import monokaiCss from 'highlight.js/styles/monokai.css?inline'
import tokyoNightCss from 'highlight.js/styles/tokyo-night-dark.css?inline'
import githubCss from 'highlight.js/styles/github.css?inline'
import atomOneLightCss from 'highlight.js/styles/atom-one-light.css?inline'
import xcodeCss from 'highlight.js/styles/xcode.css?inline'

const themes: Record<string, string> = {
  'github-dark': githubDarkCss,
  'atom-one-dark': atomOneDarkCss,
  'monokai': monokaiCss,
  'tokyo-night-dark': tokyoNightCss,
  'github': githubCss,
  'atom-one-light': atomOneLightCss,
  'xcode': xcodeCss,
}

export const THEME_OPTIONS = [
  { value: 'github-dark', label: 'GitHub Dark', mode: 'dark' },
  { value: 'atom-one-dark', label: 'Atom One Dark', mode: 'dark' },
  { value: 'monokai', label: 'Monokai', mode: 'dark' },
  { value: 'tokyo-night-dark', label: 'Tokyo Night', mode: 'dark' },
  { value: 'github', label: 'GitHub', mode: 'light' },
  { value: 'atom-one-light', label: 'Atom One Light', mode: 'light' },
  { value: 'xcode', label: 'Xcode', mode: 'light' },
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
