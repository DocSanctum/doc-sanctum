import { ref } from 'vue'
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

function getDefaultCodeTheme(appTheme: 'light' | 'dark') {
  return appTheme === 'light' ? 'github' : 'github-dark'
}

function isCodeThemeExplicit(): boolean {
  return localStorage.getItem('ds-code-theme-explicit') === 'true'
}

const codeTheme = ref(localStorage.getItem('ds-code-theme') ?? 'github-dark')

function setCodeTheme(theme: string) {
  codeTheme.value = theme
  getStyleEl().textContent = themes[theme] ?? themes['github-dark']
  localStorage.setItem('ds-code-theme', theme)
}

/** 사용자가 설정 패널에서 코드 테마를 명시적으로 고를 때 호출한다. */
export function applyCodeTheme(theme: string) {
  localStorage.setItem('ds-code-theme-explicit', 'true')
  setCodeTheme(theme)
}

/**
 * 앱 부팅 시 및 앱 테마(light/dark) 변경 시 호출한다.
 * 사용자가 코드 테마를 명시적으로 고른 적이 없으면 앱 테마에 맞는 기본 테마를 따라간다.
 */
export function initCodeTheme(appTheme: 'light' | 'dark') {
  const stored = localStorage.getItem('ds-code-theme')
  setCodeTheme(isCodeThemeExplicit() && stored ? stored : getDefaultCodeTheme(appTheme))
}

export function useCodeTheme() {
  return { codeTheme, THEME_OPTIONS, applyCodeTheme }
}
