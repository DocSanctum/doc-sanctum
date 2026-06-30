<template>
  <div class="markdown-viewer p-6 max-w-4xl mx-auto">
    <div v-if="loading" class="text-gray-400 text-sm">파일 로딩 중...</div>
    <div v-else-if="fetchError" class="text-red-400 text-sm">{{ fetchError }}</div>
    <div
      v-else
      class="prose prose-invert max-w-none"
      v-html="rendered"
      @click.prevent="handleClick"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import DOMPurify from 'dompurify'
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
.prose pre { background: #1e1e1e; border-radius: 6px; padding: 1rem; overflow-x: auto; }
.prose code { font-family: 'Fira Code', monospace; font-size: 0.875em; }
.prose table { border-collapse: collapse; width: 100%; }
.prose th, .prose td { border: 1px solid #374151; padding: 0.5rem; }
</style>
