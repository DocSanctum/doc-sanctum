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
          :class="fontSize !== 'base' ? `prose-${fontSize}` : ''"
          @click="handleClick"
          v-html="rendered"
        />
      </template>
    </div>
    <TableOfContents
      v-if="!loading && !fetchError"
      :entries="toc.entries.value"
      :active-id="toc.activeId.value"
      class="toc-column hidden lg:block"
      :class="{ 'toc-column--collapsed': tocCollapsed }"
      @select="scrollToHeading"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import { useClipboard } from '@vueuse/core'
import { api } from '../../services/api'
import { useMarkdown } from '../../composables/useMarkdown'
import { useViewerSettings } from '../../composables/useViewerSettings'
import { useToc } from '../../composables/useToc'
import { useViewerUrl } from '../../composables/useViewerUrl'
import TableOfContents from './TableOfContents.vue'
import Breadcrumb from './Breadcrumb.vue'

const props = withDefaults(
  defineProps<{ sourceId: string; filePath: string; active?: boolean }>(),
  { active: true }
)
const emit = defineEmits<{ navigate: [path: string] }>()

const { t } = useI18n()
const { render } = useMarkdown()
const { fontSize, tocCollapsed } = useViewerSettings()
const { getHeadingId, setHeadingId, buildPermalink } = useViewerUrl()
const { copy, isSupported: clipboardSupported } = useClipboard({ legacy: true, copiedDuring: 1500 })

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
.prose .code-block pre.hljs {
  margin: 0;
}
.prose pre.hljs {
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  overflow-x: auto;
}
:root.dark .prose pre.hljs { border: 1px solid #30363d; }
:root:not(.dark) .prose pre.hljs { border: 1px solid #d1d5db; }

.prose pre.hljs code {
  background: transparent;
  padding: 0;
  font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
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

/* Table */
.prose table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9em;
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
