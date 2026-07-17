<template>
  <div class="markdown-viewer-layout flex">
    <div class="markdown-viewer px-8 py-8 max-w-4xl mx-auto flex-1 min-w-0">
      <div v-if="loading" class="text-gray-400 text-sm">{{ t('viewer.markdownViewer.loading') }}</div>
      <div v-else-if="fetchError" class="text-red-400 text-sm">{{ fetchError }}</div>
      <template v-else>
        <Breadcrumb :path="filePath" />
        <div
          ref="contentRef"
          class="prose dark:prose-invert max-w-none"
          :class="[fontSize !== 'base' ? `prose-${fontSize}` : '', { 'show-line-numbers': lineNumbers }]"
          @click="handleClick"
          v-html="rendered"
        />
      </template>
    </div>
    <TableOfContents
      v-if="!loading && !fetchError"
      :pane-id="paneId"
      :entries="toc.entries.value"
      :active-id="toc.activeId.value"
      class="toc-column hidden lg:block"
      :class="{ 'toc-column--collapsed': isTocCollapsed(paneId) }"
      @select="scrollToHeading"
    />
  </div>
  <div
    v-if="fullscreenMermaidSvg"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-8"
    @click.self="closeMermaidFullscreen"
  >
    <div class="mermaid-fullscreen-content">
      <button
        type="button"
        class="mermaid-fullscreen-close"
        :title="t('viewer.markdown.exitFullscreen')"
        @click="closeMermaidFullscreen"
      >✕</button>
      <div class="mermaid-fullscreen-svg" v-html="sanitizedFullscreenMermaidSvg" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import { useClipboard, onKeyStroke } from '@vueuse/core'
import { api } from '../../services/api'
import { useMarkdown } from '../../composables/useMarkdown'
import { useViewerSettings } from '../../composables/useViewerSettings'
import { useTheme } from '../../composables/useTheme'
import { useToc } from '../../composables/useToc'
import { useViewerUrl } from '../../composables/useViewerUrl'
import { useSearchReveal } from '../../composables/useSearchReveal'
import type { PaneId } from '../../types'
import TableOfContents from './TableOfContents.vue'
import Breadcrumb from './Breadcrumb.vue'

const props = withDefaults(
  defineProps<{ paneId: PaneId; sourceId: string; filePath: string; active?: boolean }>(),
  { active: true }
)
const emit = defineEmits<{ navigate: [path: string] }>()

const { t } = useI18n()
const { render } = useMarkdown()
const { fontSize, isTocCollapsed, lineNumbers } = useViewerSettings()
const { theme } = useTheme()
const { getHeadingId, setHeadingId, buildPermalink } = useViewerUrl()
const { copy, isSupported: clipboardSupported } = useClipboard({ legacy: true, copiedDuring: 1500 })
const { revealTarget, revealToken } = useSearchReveal()

const raw = ref('')
const loading = ref(false)
const fetchError = ref('')
const contentRef = ref<HTMLElement | null>(null)
const toc = useToc(contentRef)

// 문서 전환/최초 로드 복원 중에는 useToc의 "첫 헤딩 기본 활성화" 부작용이
// URL 해시(퍼머링크로 들어온 값)를 덮어쓰지 않도록 스크롤스파이→URL 동기화를 잠시 멈춘다.
let suppressHashSync = false

const rendered = computed(() =>
  DOMPurify.sanitize(render(raw.value), { USE_PROFILES: { html: true } })
)

// Mermaid diagrams render on the client, outside the markdown-it → DOMPurify
// pipeline: useMarkdown.ts emits a plain `<div class="mermaid">source</div>`
// (mermaid.js's own convention) and this walks the DOM after each render to
// turn those into SVG. Loaded lazily since mermaid is a large dependency
// that most documents never need.
let mermaid: typeof import('mermaid')['default'] | null = null

async function renderMermaidBlocks() {
  if (!contentRef.value) return
  const blocks = Array.from(contentRef.value.querySelectorAll<HTMLElement>('.mermaid-block .mermaid'))
  if (blocks.length === 0) return
  if (!mermaid) mermaid = (await import('mermaid')).default
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: theme.value === 'light' ? 'default' : 'dark',
  })
  for (const el of blocks) {
    // The hidden <code> sibling always holds the original source, so a
    // previous run's SVG output can be discarded and re-parsed from scratch
    // — needed both to retry after an edit and to re-render when the app
    // theme changes.
    const source = el.closest('.mermaid-block')?.querySelector('code')?.textContent ?? ''
    el.removeAttribute('data-processed')
    el.textContent = source
    try {
      await mermaid.run({ nodes: [el] })
      // mermaid defaults every diagram type to useMaxWidth: true, which sets
      // width="100%" on the SVG so it shrinks (text included) to fit a
      // narrow reading pane instead of staying legible. Re-pointing the SVG
      // at its own viewBox size (what useMaxWidth: false would produce)
      // keeps it at native size and lets the .mermaid-block's overflow-x:
      // auto scroll it horizontally instead — without having to opt every
      // one of mermaid's ~25 diagram-specific config namespaces out
      // individually.
      const svg = el.querySelector('svg')
      const viewBox = svg?.getAttribute('viewBox')?.split(/\s+/).map(Number)
      if (svg && viewBox?.length === 4) {
        svg.setAttribute('width', String(viewBox[2]))
        svg.setAttribute('height', String(viewBox[3]))
      }
    } catch {
      el.textContent = source
      el.classList.add('mermaid-error')
      el.setAttribute('data-mermaid-error-label', t('viewer.markdown.mermaidError'))
    }
  }
}

// Fullscreen preview reuses the already-rendered SVG (outerHTML, not the
// original mermaid source) so it doesn't need a second mermaid.run() call —
// same reasoning as the copy button reusing the hidden <code> sibling.
const fullscreenMermaidSvg = ref<string | null>(null)
// mermaid renders diagram/label text as HTML inside <foreignObject>, which
// DOMPurify's svg profile strips by default (a common XSS vector for
// arbitrary SVG) — ADD_TAGS opts it back in for this already-mermaid-
// generated markup, or every node/edge label would render as an empty box.
const sanitizedFullscreenMermaidSvg = computed(() =>
  fullscreenMermaidSvg.value
    ? DOMPurify.sanitize(fullscreenMermaidSvg.value, {
        USE_PROFILES: { svg: true, svgFilters: true },
        ADD_TAGS: ['foreignObject'],
      })
    : ''
)

function openMermaidFullscreen(block: HTMLElement) {
  const svg = block.querySelector('svg')
  if (svg) fullscreenMermaidSvg.value = svg.outerHTML
}

function closeMermaidFullscreen() {
  fullscreenMermaidSvg.value = null
}

onKeyStroke('Escape', () => {
  if (fullscreenMermaidSvg.value) closeMermaidFullscreen()
})

watch(rendered, () => nextTick(() => renderMermaidBlocks()))
watch(theme, () => nextTick(() => renderMermaidBlocks()))

async function load() {
  if (!props.sourceId || !props.filePath) return
  loading.value = true
  fetchError.value = ''
  suppressHashSync = true
  try {
    raw.value = await api.getFileContent(props.sourceId, props.filePath)
  } catch (e: any) {
    fetchError.value = e.message ?? t('viewer.markdownViewer.notFound')
    loading.value = false
    suppressHashSync = false
    return
  }
  // contentRef는 loading이 false가 되어야 마운트되므로, 헤딩을 조회하는
  // restoreScrollFromUrl()/toc.refresh()보다 먼저 loading을 내려야 한다.
  // 스크롤 복원은 반드시 toc.refresh()(=IntersectionObserver 관찰 시작)보다
  // 먼저 실행해야 한다 — observe() 호출 직후 발생하는 최초 콜백은 "관찰을
  // 시작한 시점"의 레이아웃을 기준으로 판정하므로, 관찰 시작 후에 스크롤하면
  // 그 초기 콜백이 스크롤 이전(문서 맨 위) 상태를 활성 헤딩으로 오판해
  // 되돌려버린다.
  loading.value = false
  await nextTick()
  // 여러 패널이 동시에 열려 있을 때 URL 해시는 활성 패널 하나만 소유한다
  // (research.md #4) — 비활성 패널은 해시를 읽지도 쓰지도 않는다.
  if (props.active) restoreScrollFromUrl()
  await toc.refresh(props.active ? getHeadingId() : null)
  suppressHashSync = false
  // If the document was just opened by picking a search result (008-search),
  // apply any reveal signal that hasn't been handled yet — since load() is
  // async, the watch(revealToken, ...) below can run before the content
  // actually renders, so check again here once loading finishes to close
  // that race.
  tryApplyPendingReveal()
}

watch(() => [props.sourceId, props.filePath], load, { immediate: true })

watch(toc.activeId, (id) => {
  if (suppressHashSync || !id || !props.active) return
  setHeadingId(id)
})

// 패널이 새로 활성화되면, 그 시점의 활성 헤딩으로 해시 소유권을 즉시 넘겨받는다.
watch(
  () => props.active,
  (isActive) => {
    if (isActive && toc.activeId.value) setHeadingId(toc.activeId.value)
  }
)

function restoreScrollFromUrl() {
  const headingId = getHeadingId()
  if (!headingId || !contentRef.value) return
  const target = contentRef.value.querySelector<HTMLElement>(`#${CSS.escape(headingId)}`)
  target?.scrollIntoView({ behavior: 'instant' as ScrollBehavior, block: 'start' })
}

function scrollToHeading(id: string) {
  const target = contentRef.value?.querySelector<HTMLElement>(`#${CSS.escape(id)}`)
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  toc.activeId.value = id
  setHeadingId(id)
}

// Finds the block element with the closest data-line (as set by
// useMarkdown.ts) at or before the target line — i.e. the element that
// actually contains that line. Candidates are in DOM order == source order,
// so the last one that still satisfies the condition is the answer.
function scrollToLine(lineNumber: number) {
  if (!contentRef.value) return
  const candidates = contentRef.value.querySelectorAll<HTMLElement>('[data-line]')
  let target: HTMLElement | null = null
  for (const el of candidates) {
    if (Number(el.dataset.line) <= lineNumber) target = el
    else break
  }
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.classList.add('search-match-flash')
  window.setTimeout(() => target?.classList.remove('search-match-flash'), 1200)
}

function tryApplyPendingReveal() {
  if (!props.active) return
  const target = revealTarget.value
  if (!target) return
  // Check whether the reveal signal is actually meant for the document this
  // pane is showing right now. Since the target carries sourceId/filePath,
  // this is safe to check regardless of whether load() is still in flight
  // (MarkdownViewer just mounting) or the same document was already open and
  // load() never re-ran.
  if (target.sourceId !== props.sourceId || target.filePath !== props.filePath) return
  scrollToLine(target.lineNumber)
}

// immediate: reveal() may have already been called (and revealToken already
// incremented) before this component mounted and this watch was registered
// (the same race useTreeReveal.ts's reveal-token handles) — check once more
// at mount time to close that race.
watch(
  revealToken,
  () => {
    // Skip here if load() is in flight (switching to a different document) —
    // its own completion will call tryApplyPendingReveal() once more.
    if (loading.value) return
    nextTick(() => tryApplyPendingReveal())
  },
  { immediate: true }
)

function flashFeedback(el: HTMLElement, ok: boolean) {
  const original = el.textContent
  el.textContent = ok ? t('common.copied') : t('common.copyFailed')
  el.classList.add(ok ? 'copy-ok' : 'copy-fail')
  window.setTimeout(() => {
    el.textContent = original
    el.classList.remove(ok ? 'copy-ok' : 'copy-fail')
  }, 1500)
}

async function copyToClipboard(el: HTMLElement, text: string) {
  if (!clipboardSupported.value) {
    flashFeedback(el, false)
    return
  }
  try {
    await copy(text)
    flashFeedback(el, true)
  } catch {
    flashFeedback(el, false)
  }
}

function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement

  const copyBtn = target.closest('.code-copy-btn') as HTMLElement | null
  if (copyBtn) {
    e.preventDefault()
    const code = copyBtn.closest('.code-block')?.querySelector('code')?.textContent ?? ''
    copyToClipboard(copyBtn, code)
    return
  }

  const fullscreenBtn = target.closest('.mermaid-fullscreen-btn') as HTMLElement | null
  if (fullscreenBtn) {
    e.preventDefault()
    const block = fullscreenBtn.closest('.mermaid-block') as HTMLElement | null
    if (block) openMermaidFullscreen(block)
    return
  }

  const permalinkAnchor = target.closest('a.header-anchor') as HTMLElement | null
  if (permalinkAnchor) {
    e.preventDefault()
    const heading = permalinkAnchor.closest('h1, h2, h3, h4, h5, h6') as HTMLElement | null
    if (heading?.id) {
      const url = buildPermalink(props.sourceId, props.filePath, heading.id)
      copyToClipboard(permalinkAnchor, url)
    }
    return
  }

  const anchor = target.closest('a')
  if (!anchor) return
  const href = anchor.getAttribute('href') ?? ''

  if (href.startsWith('http://') || href.startsWith('https://')) {
    e.preventDefault()
    window.open(href, '_blank', 'noopener,noreferrer')
    return
  }

  if (href.startsWith('#')) return

  if (href.endsWith('.md')) {
    e.preventDefault()
    emit('navigate', href)
  }
}
</script>

<style>
/* Layout: content + TOC column */
.markdown-viewer-layout {
  min-height: 100%;
}

/* Break at word/phrase boundaries for Korean text instead of mid-syllable;
   overflow-wrap still allows unbreakable tokens (long URLs) to wrap so they
   don't overflow the pane. Reset inside code, which needs its own
   monospace-preserving behavior instead. */
.prose {
  word-break: keep-all;
  overflow-wrap: break-word;
}
.prose pre,
.prose code {
  word-break: normal;
  overflow-wrap: normal;
}
.toc-column {
  width: 14rem;
  flex-shrink: 0;
  padding: 2rem 1.5rem 2rem 0;
}
.toc-column--collapsed {
  width: auto;
  padding-right: 0.5rem;
}

/* Code blocks */
.prose .code-block {
  position: relative;
  margin: 1.5rem 0;
}
/* One scrolling container for the whole block (numbers + code together),
   instead of two independently laid out columns kept in sync by matching
   CSS values across them. Each source line is now a single .code-line row
   (below) containing both its number and its code as flex siblings, so the
   browser lays them out together — there's nothing left that can drift
   apart from sub-pixel rounding, font substitution, or browser zoom, since
   there's only one row box being measured, not two.
   `.hljs` is applied here (not on a nested <pre>) so the active code-theme
   stylesheet's `.hljs { background; color }` rule paints the container
   directly; `.code-line`/`.code-line-number` below relay it downward via
   `background: inherit` so the sticky number gutter (see below) matches
   whatever theme is active without hardcoding a color here. */
.prose .code-block-body {
  overflow-x: auto;
  border-radius: 8px;
  padding: 1.25rem 0;
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  font-size: 0.875rem;
  line-height: 1.3125rem;
  /* Thin themed horizontal scrollbar for long lines, matching
     .viewer-pane-scroll in style.css instead of the browser default. */
  scrollbar-width: thin;
  scrollbar-color: #d1d5db transparent;
}
.prose-sm .code-block-body {
  font-size: 0.75rem;
  line-height: 1.125rem;
}
.prose-lg .code-block-body {
  font-size: 1rem;
  line-height: 1.5rem;
}
.prose .code-block-body::-webkit-scrollbar {
  height: 8px;
}
.prose .code-block-body::-webkit-scrollbar-track {
  background: transparent;
}
.prose .code-block-body::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}
.prose .code-block-body::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
:root.dark .prose .code-block-body {
  scrollbar-color: #374151 transparent;
}
:root.dark .prose .code-block-body::-webkit-scrollbar-thumb {
  background: #374151;
}
:root.dark .prose .code-block-body::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}
:root.dark .prose .code-block-body { border: 1px solid #30363d; }
/* Light mode intentionally overrides whatever background the active
   light hljs theme (github/atom-one-light/xcode) ships with, for a
   consistent app-gray look; dark mode keeps each dark theme's own
   background as-is. Higher specificity than the injected `.hljs` rule
   (which is a bare class selector) wins regardless of stylesheet order. */
:root:not(.dark) .prose .code-block-body { border: 1px solid #d1d5db; background: #f3f4f6; }

.prose .code-line {
  display: flex;
  background: inherit;
}
.prose .code-line-content {
  white-space: pre;
  padding: 0 1.5rem;
}
/* Sticky, not a separate scroll container: stays pinned to the left edge of
   .code-block-body's scrollport while .code-line-content scrolls under it,
   so numbers and code can never end up in different scroll positions.
   `background: inherit` relays .code-line's (itself relayed from
   .code-block-body) background so scrolled-under code doesn't show through. */
.prose .code-line-number {
  display: none;
  position: sticky;
  left: 0;
  z-index: 1;
  flex-shrink: 0;
  min-width: 3ch;
  padding: 0 0.75rem 0 1.25rem;
  text-align: right;
  user-select: none;
  color: #6b7280;
  background: inherit;
}
.prose.show-line-numbers .code-line-number {
  display: inline-block;
}
.prose.show-line-numbers .code-line-content {
  padding-left: 0;
}

/* Mermaid diagrams: useMarkdown.ts emits <div class="mermaid">source</div>
   here; MarkdownViewer.vue renders it into SVG client-side after mount.
   The overflow-x: auto container is .mermaid-block-scroll, an inner wrapper
   around just the diagram — not .mermaid-block itself — so
   .mermaid-block-actions (a non-scrolling sibling) stays pinned to the
   corner instead of panning away with the diagram on horizontal scroll. */
.prose .mermaid-block {
  padding: 1.5rem;
  border-radius: 8px;
}
:root.dark .prose .mermaid-block { border: 1px solid #30363d; background: #161b22; }
:root:not(.dark) .prose .mermaid-block { border: 1px solid #d1d5db; background: #f9fafb; }
.prose .mermaid-block-scroll {
  display: flex;
  justify-content: center;
  overflow-x: auto;
}
.prose .mermaid-block .mermaid svg {
  max-width: 100%;
  height: auto;
}
.prose .mermaid-error {
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  font-size: 0.8em;
  white-space: pre-wrap;
  color: #ef4444;
}
.prose .mermaid-error::before {
  content: attr(data-mermaid-error-label);
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

/* Mermaid blocks show the copy button plus a fullscreen button, sharing one
   flex wrapper (see useMarkdown.ts) instead of each being independently
   absolutely-positioned, so .code-copy-btn's own position/top/right reset
   to let the wrapper place it. */
.prose .mermaid-block-actions {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: flex;
  gap: 0.4rem;
}
.prose .mermaid-block-actions .code-copy-btn {
  position: static;
}
.prose .mermaid-fullscreen-btn {
  font-size: 0.7rem;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.08);
  color: #9ca3af;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease;
}
.prose .code-block:hover .mermaid-fullscreen-btn,
.prose .mermaid-fullscreen-btn:focus-visible {
  opacity: 1;
}
.prose .mermaid-fullscreen-btn:hover {
  color: #3b82f6;
  border-color: #3b82f6;
}

.mermaid-fullscreen-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  padding: 2rem;
  border-radius: 8px;
  overflow: auto;
}
:root.dark .mermaid-fullscreen-content { background: #161b22; }
:root:not(.dark) .mermaid-fullscreen-content { background: #f9fafb; }
.mermaid-fullscreen-close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  font-size: 0.9rem;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.08);
  color: #9ca3af;
  cursor: pointer;
}
.mermaid-fullscreen-close:hover {
  color: #ef4444;
  border-color: #ef4444;
}
.mermaid-fullscreen-svg svg {
  display: block;
  max-width: none;
}

.prose .code-copy-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  font-size: 0.7rem;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.08);
  color: #9ca3af;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease;
}
.prose .code-block:hover .code-copy-btn,
.prose .code-copy-btn:focus-visible {
  opacity: 1;
}
.prose .code-copy-btn:hover {
  color: #3b82f6;
  border-color: #3b82f6;
}
.prose .code-copy-btn.copy-ok { color: #22c55e; border-color: #22c55e; opacity: 1; }
.prose .code-copy-btn.copy-fail { color: #ef4444; border-color: #ef4444; opacity: 1; }

/* Heading permalink */
.prose .header-anchor {
  margin-left: 0.4em;
  opacity: 0;
  text-decoration: none;
  font-weight: 400;
  color: #6b7280;
  transition: opacity 0.15s ease;
}
.prose h1:hover .header-anchor,
.prose h2:hover .header-anchor,
.prose h3:hover .header-anchor,
.prose h4:hover .header-anchor,
.prose h5:hover .header-anchor,
.prose h6:hover .header-anchor,
.prose .header-anchor:focus-visible {
  opacity: 1;
}
.prose .header-anchor.copy-ok { opacity: 1; color: #22c55e; }
.prose .header-anchor.copy-fail { opacity: 1; color: #ef4444; }

/* Inline code */
:root.dark .prose :not(pre) > code {
  background: #1f2937;
  border: 1px solid #374151;
  color: #e5e7eb;
}
:root:not(.dark) .prose :not(pre) > code {
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  color: #1f2937;
}
.prose :not(pre) > code {
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
}
.prose :not(pre) > code::before,
.prose :not(pre) > code::after {
  content: none;
}

/* Table: keep the table's own natural width and let it scroll horizontally
   rather than squeezing columns, so wide tables don't break the pane layout
   (especially in narrow split-view panes). */
.prose table {
  display: block;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  font-size: 0.9em;
  /* Thin themed horizontal scrollbar for wide tables, matching
     .prose .code-block-body instead of the browser default. */
  scrollbar-width: thin;
  scrollbar-color: #d1d5db transparent;
}
.prose table::-webkit-scrollbar {
  height: 8px;
}
.prose table::-webkit-scrollbar-track {
  background: transparent;
}
.prose table::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}
.prose table::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
:root.dark .prose table {
  scrollbar-color: #374151 transparent;
}
:root.dark .prose table::-webkit-scrollbar-thumb {
  background: #374151;
}
:root.dark .prose table::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}
:root.dark .prose thead th { background: #1f2937; border-bottom: 2px solid #374151; }
:root:not(.dark) .prose thead th { background: #f9fafb; border-bottom: 2px solid #e5e7eb; }
:root.dark .prose th, :root.dark .prose td { border: 1px solid #374151; }
:root:not(.dark) .prose th, :root:not(.dark) .prose td { border: 1px solid #e5e7eb; }
.prose th, .prose td { padding: 0.6rem 0.9rem; }
:root.dark .prose tbody tr:hover { background: #1a2233; }
:root:not(.dark) .prose tbody tr:hover { background: #f9fafb; }

/* Task list */
.prose .task-list-item {
  list-style: none;
  padding-left: 0;
}
.prose .task-list-item input[type="checkbox"] {
  margin-right: 0.5rem;
  accent-color: #3b82f6;
}

/* Footnotes */
.prose .footnotes {
  border-top: 1px solid #374151;
  margin-top: 2rem;
  padding-top: 1rem;
  font-size: 0.85em;
  color: #9ca3af;
}

/* Search reveal (008-search) — same pattern as TreeNode.vue's tree-reveal-flash */
.prose .search-match-flash {
  animation: search-match-flash 1.2s ease-out;
}
@keyframes search-match-flash {
  0%,
  40% {
    background-color: rgba(59, 130, 246, 0.35);
  }
  100% {
    background-color: transparent;
  }
}

/* Blockquote */
.prose blockquote {
  border-left: 4px solid #3b82f6;
  border-radius: 0 6px 6px 0;
  padding: 0.75rem 1.25rem;
}
:root.dark .prose blockquote { background: #111827; color: #d1d5db; }
:root:not(.dark) .prose blockquote { background: #eff6ff; color: #1e3a5f; }
.prose blockquote p { margin: 0; }
</style>
