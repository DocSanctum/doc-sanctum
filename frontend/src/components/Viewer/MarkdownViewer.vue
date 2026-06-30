<template>
  <div class="markdown-viewer px-8 py-8 max-w-4xl mx-auto">
    <div v-if="loading" class="text-gray-400 text-sm">파일 로딩 중...</div>
    <div v-else-if="fetchError" class="text-red-400 text-sm">{{ fetchError }}</div>
    <div
      v-else
      class="prose prose-invert prose-lg max-w-none"
      v-html="rendered"
      @click.prevent="handleClick"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import DOMPurify from 'dompurify'
import 'highlight.js/styles/github-dark.css'
import { api } from '../../services/api'
import { useMarkdown } from '../../composables/useMarkdown'

const props = defineProps<{ sourceId: string; filePath: string }>()
const emit = defineEmits<{ navigate: [path: string] }>()

const { render } = useMarkdown()
const raw = ref('')
const loading = ref(false)
const fetchError = ref('')

const rendered = computed(() =>
  DOMPurify.sanitize(render(raw.value), { USE_PROFILES: { html: true } })
)

async function load() {
  if (!props.sourceId || !props.filePath) return
  loading.value = true
  fetchError.value = ''
  try {
    raw.value = await api.getFileContent(props.sourceId, props.filePath)
  } catch (e: any) {
    fetchError.value = e.message ?? '파일을 불러올 수 없습니다'
  } finally {
    loading.value = false
  }
}

watch(() => [props.sourceId, props.filePath], load, { immediate: true })

function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const anchor = target.closest('a')
  if (!anchor) return
  const href = anchor.getAttribute('href') ?? ''
  if (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('#')) return
  if (href.endsWith('.md')) {
    emit('navigate', href)
  }
}
</script>

<style>
/* Heading anchors */
.prose .header-anchor {
  opacity: 0;
  margin-left: 0.5rem;
  text-decoration: none;
  transition: opacity 0.2s;
}
.prose h1:hover .header-anchor,
.prose h2:hover .header-anchor,
.prose h3:hover .header-anchor,
.prose h4:hover .header-anchor {
  opacity: 0.5;
}

/* Code blocks */
.prose pre.hljs {
  background: #0d1117;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  overflow-x: auto;
  margin: 1.5rem 0;
  border: 1px solid #30363d;
}
.prose pre.hljs code {
  background: transparent;
  padding: 0;
  font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
}

/* Inline code */
.prose :not(pre) > code {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  color: #e5e7eb;
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
.prose thead th {
  background: #1f2937;
  border-bottom: 2px solid #374151;
}
.prose th, .prose td {
  border: 1px solid #374151;
  padding: 0.6rem 0.9rem;
}
.prose tbody tr:hover {
  background: #1a2233;
}

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
  background: #111827;
  border-radius: 0 6px 6px 0;
  padding: 0.75rem 1.25rem;
  color: #d1d5db;
}
.prose blockquote p {
  margin: 0;
}
</style>
