<template>
  <div class="max-w-xl mx-auto px-8 py-10">
    <h1 class="text-lg font-semibold mb-8 text-gray-900 dark:text-white">설정</h1>

    <!-- App theme -->
    <section class="mb-8">
      <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">앱 테마</h2>
      <div class="flex gap-3">
        <button
          v-for="t in appThemes"
          :key="t.value"
          class="flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors"
          :class="theme === t.value
            ? 'bg-blue-600 border-blue-500 text-white'
            : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-400'"
          @click="applyTheme(t.value)"
        >
          <span>{{ t.icon }}</span>
          {{ t.label }}
        </button>
      </div>
    </section>

    <!-- Font size -->
    <section class="mb-8">
      <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">뷰어 폰트 크기</h2>
      <div class="flex gap-3">
        <button
          v-for="size in fontSizes"
          :key="size.value"
          class="px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors"
          :class="fontSize === size.value
            ? 'bg-blue-600 border-blue-500 text-white'
            : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-400'"
          @click="setFontSize(size.value)"
        >
          {{ size.label }}
        </button>
      </div>
    </section>

    <!-- Code theme -->
    <section class="mb-8">
      <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">코드 하이라이트 테마</h2>
      <div class="grid grid-cols-2 gap-2">
        <button
          v-for="t in THEME_OPTIONS"
          :key="t.value"
          class="flex items-center justify-between px-3 py-2 rounded-lg border text-sm transition-colors text-left"
          :class="currentCodeTheme === t.value
            ? 'bg-blue-600 border-blue-500 text-white'
            : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-400'"
          @click="selectCodeTheme(t.value)"
        >
          <span>{{ t.label }}</span>
          <span
            class="text-xs px-1.5 py-0.5 rounded"
            :class="currentCodeTheme === t.value
              ? 'bg-blue-500 text-blue-100'
              : t.mode === 'dark' ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-500'"
          >{{ t.mode === 'dark' ? '다크' : '라이트' }}</span>
        </button>
      </div>
    </section>

    <!-- Source polling -->
    <section v-if="remoteSources.length > 0" class="mb-8">
      <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">소스 폴링 주기</h2>
      <div class="space-y-2">
        <div
          v-for="source in remoteSources"
          :key="source.id"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
        >
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ source.name }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ source.path }}</div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <input
              :value="pollingValues[source.id]"
              type="number"
              min="30"
              class="w-20 text-xs text-right bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-500"
              @input="pollingValues[source.id] = Number(($event.target as HTMLInputElement).value)"
            />
            <span class="text-xs text-gray-400 dark:text-gray-500">초</span>
            <button
              class="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
              :disabled="pollingValues[source.id] === source.polling_interval_seconds"
              @click="savePoll(source.id)"
            >저장</button>
          </div>
        </div>
      </div>
    </section>

    <!-- MCP Server -->
    <section class="mb-8">
      <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">MCP Server</h2>
      <div v-if="mcpLoading" class="text-sm text-gray-400 dark:text-gray-500">로딩 중...</div>
      <div v-else-if="mcpStatus" class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <!-- Header row -->
        <div class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800">
          <div class="flex items-center gap-2">
            <span
              class="inline-block w-2 h-2 rounded-full"
              :class="mcpStatus.enabled ? 'bg-green-500' : 'bg-gray-400'"
            />
            <span class="text-sm font-medium text-gray-900 dark:text-white">
              {{ mcpStatus.enabled ? 'Enabled' : 'Disabled' }}
            </span>
          </div>
          <button
            class="text-xs px-3 py-1.5 rounded-md border font-medium transition-colors"
            :class="mcpStatus.enabled
              ? 'border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
              : 'border-green-300 dark:border-green-700 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20'"
            @click="toggleMcp"
          >
            {{ mcpStatus.enabled ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <!-- Endpoints -->
        <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-2">
          <div v-for="ep in endpoints" :key="ep.label">
            <div class="flex items-center gap-1.5 mb-1">
              <span class="text-xs text-gray-500 dark:text-gray-400">{{ ep.label }}</span>
              <span class="text-xs px-1 rounded"
                :class="ep.badge === 'new' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500'"
              >{{ ep.badge }}</span>
            </div>
            <div class="flex items-center gap-2">
              <code class="flex-1 text-xs bg-gray-100 dark:bg-gray-800 rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 truncate font-mono">
                {{ ep.url }}
              </code>
              <button
                class="text-xs px-2 py-1.5 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shrink-0"
                @click="copyUrl(ep.url, ep.label)"
              >{{ copiedLabel === ep.label ? '✓ 복사됨' : '복사' }}</button>
            </div>
          </div>
        </div>

        <!-- Tools -->
        <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div class="text-xs text-gray-500 dark:text-gray-400 mb-2">Tools ({{ mcpStatus.tools.length }})</div>
          <div class="space-y-1.5">
            <div
              v-for="tool in mcpStatus.tools"
              :key="tool.name"
              class="flex items-start gap-2"
            >
              <code class="text-xs bg-gray-100 dark:bg-gray-800 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded font-mono shrink-0">{{ tool.name }}</code>
              <span class="text-xs text-gray-500 dark:text-gray-400 pt-0.5">{{ tool.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Version & Changelog -->
    <section class="pt-6 border-t border-gray-200 dark:border-gray-700">
      <div class="flex items-baseline gap-3 mb-4">
        <span class="text-xl font-bold text-gray-900 dark:text-white">DocSanctum</span>
        <span class="text-sm font-mono text-blue-500 dark:text-blue-400">v{{ currentVersion }}</span>
      </div>

      <div class="space-y-4">
        <div
          v-for="entry in changelog"
          :key="entry.version"
          class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
        >
          <button
            class="w-full flex items-center justify-between px-4 py-2.5 text-left bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            @click="toggleVersion(entry.version)"
          >
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono font-semibold text-gray-900 dark:text-white">v{{ entry.version }}</span>
              <span
                v-if="entry.version === currentVersion"
                class="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded"
              >현재</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs text-gray-400 dark:text-gray-500">{{ entry.date }}</span>
              <span class="text-gray-400 dark:text-gray-500 text-xs">{{ openVersions.has(entry.version) ? '▲' : '▼' }}</span>
            </div>
          </button>
          <ul v-if="openVersions.has(entry.version)" class="px-4 py-3 space-y-1.5 bg-white dark:bg-gray-900">
            <li
              v-for="(change, i) in entry.changes"
              :key="i"
              class="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300"
            >
              <span class="text-blue-400 mt-0.5 shrink-0">·</span>
              {{ change }}
            </li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useTheme } from '../../composables/useTheme'
import { useViewerSettings } from '../../composables/useViewerSettings'
import { applyCodeTheme, THEME_OPTIONS } from '../../composables/useCodeTheme'
import { useSources } from '../../composables/useSources'
import { changelog } from '../../data/changelog'
import { api } from '../../services/api'
import type { McpStatus } from '../../types'
import pkg from '../../../package.json'

const { theme, applyTheme } = useTheme()
const { fontSize, setFontSize } = useViewerSettings()
const { sourcesQuery, patch } = useSources()

const currentVersion = pkg.version
const currentCodeTheme = ref(localStorage.getItem('ds-code-theme') ?? 'github-dark')

const DEFAULT_POLL: Record<string, number> = { github: 600, http: 300, localhost: 300 }

const remoteSources = computed(() =>
  (sourcesQuery.data.value ?? []).filter(s => s.type !== 'local')
)

const pollingValues = reactive<Record<string, number>>({})

watch(remoteSources, (sources) => {
  for (const s of sources) {
    if (!(s.id in pollingValues)) {
      pollingValues[s.id] = s.polling_interval_seconds ?? DEFAULT_POLL[s.type] ?? 300
    }
  }
}, { immediate: true })

function savePoll(id: string) {
  patch.mutate({ id, data: { polling_interval_seconds: pollingValues[id] } })
}

const appThemes = [
  { value: 'dark' as const, label: 'Dark', icon: '🌙' },
  { value: 'light' as const, label: 'Light', icon: '☀️' },
]

const fontSizes = [
  { label: '소', value: 'sm' },
  { label: '중', value: 'base' },
  { label: '대', value: 'lg' },
]

const openVersions = ref(new Set([currentVersion]))

function toggleVersion(version: string) {
  if (openVersions.value.has(version)) {
    openVersions.value.delete(version)
  } else {
    openVersions.value.add(version)
  }
}

function selectCodeTheme(value: string) {
  currentCodeTheme.value = value
  applyCodeTheme(value)
}

// MCP
const mcpStatus = ref<McpStatus | null>(null)
const mcpLoading = ref(false)
const copiedLabel = ref('')

function backendOrigin() {
  const h = window.location.hostname
  return h === 'localhost' || h === '127.0.0.1'
    ? `http://${h}:8000`
    : window.location.origin
}

const endpoints = computed(() => {
  const o = backendOrigin()
  return [
    { label: 'Streamable HTTP', url: `${o}${mcpStatus.value?.http_url ?? '/mcp-http'}`, badge: 'new' },
    { label: 'SSE', url: `${o}${mcpStatus.value?.sse_url ?? '/mcp/sse'}`, badge: 'legacy' },
  ]
})

async function loadMcpStatus() {
  mcpLoading.value = true
  try {
    mcpStatus.value = await api.getMcpStatus()
  } finally {
    mcpLoading.value = false
  }
}

async function toggleMcp() {
  if (!mcpStatus.value) return
  mcpStatus.value = await api.setMcpEnabled(!mcpStatus.value.enabled)
}

async function copyUrl(url: string, label: string) {
  await navigator.clipboard.writeText(url)
  copiedLabel.value = label
  setTimeout(() => { copiedLabel.value = '' }, 2000)
}

onMounted(loadMcpStatus)
</script>
