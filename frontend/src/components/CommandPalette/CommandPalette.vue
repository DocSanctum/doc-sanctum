<template>
  <div
    v-if="search.isOpen.value"
    class="fixed inset-0 bg-black/50 flex items-start justify-center z-50 pt-24"
    @click.self="close"
  >
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-xl mx-4 flex flex-col max-h-[70vh]">
      <div class="p-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <input
          ref="inputRef"
          class="input w-full"
          type="text"
          :value="search.query.value"
          :placeholder="t('search.placeholder')"
          :aria-label="t('search.ariaLabel')"
          @input="search.setQuery(($event.target as HTMLInputElement).value)"
          @keydown.down.prevent="moveActive(1)"
          @keydown.up.prevent="moveActive(-1)"
          @keydown.enter.prevent="selectActive"
        />
      </div>
      <div class="overflow-y-auto flex-1 p-1">
        <p v-if="noSources" class="text-sm text-gray-400 px-3 py-4">{{ t('search.noSources') }}</p>
        <template v-else-if="search.loading.value">
          <p class="text-sm text-gray-400 px-3 py-4">{{ t('search.loading') }}</p>
        </template>
        <template v-else>
          <p
            v-if="search.query.value.trim() && search.results.value.length === 0"
            class="text-sm text-gray-400 px-3 py-4"
          >{{ t('search.noResults') }}</p>
          <template v-for="(match, index) in search.results.value" :key="`${match.source_id}:${match.path}:${match.line_number}:${index}`">
            <SearchResultItem
              :match="match"
              :active="index === search.activeIndex.value"
              @select="selectResult(match)"
              @hover="search.activeIndex.value = index"
            />
            <p v-if="isLastInGroup(match, index) && isGroupTruncated(match)" class="text-xs text-gray-400 px-3 py-1">
              {{ t('search.moreMatches') }}
            </p>
          </template>
        </template>
        <div v-if="search.warnings.value.length" class="border-t border-gray-200 dark:border-gray-700 mt-1 pt-1">
          <p v-for="(w, i) in search.warnings.value" :key="i" class="text-xs text-amber-500 px-3 py-1">
            {{ t('search.warning', { name: w.source_name ?? '', message: w.message }) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { onKeyStroke } from '@vueuse/core'
import { useSearch } from '../../composables/useSearch'
import { useSearchReveal } from '../../composables/useSearchReveal'
import { usePanes } from '../../composables/usePanes'
import { useSources } from '../../composables/useSources'
import SearchResultItem from './SearchResultItem.vue'
import type { SearchMatch } from '../../types'

// backend/app/mcp/tools/search_documents.py의 MAX_MATCHES_PER_FILE과 일치해야
// 한다(FR-012) — API 응답에는 별도의 "더 있음" 플래그가 없어 문서당 매치 개수가
// 이 상수에 도달했는지로 잘림 여부를 추정한다.
const MAX_MATCHES_PER_FILE = 10

const { t } = useI18n()
const search = useSearch()
const { reveal } = useSearchReveal()
const { openInActivePane } = usePanes()
const { sourcesQuery } = useSources()

const inputRef = ref<HTMLInputElement | null>(null)

const noSources = computed(() => (sourcesQuery.data.value?.length ?? 0) === 0)

const groupCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const m of search.results.value) {
    const key = `${m.source_id}:${m.path}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return counts
})

function isGroupTruncated(match: SearchMatch): boolean {
  return (groupCounts.value.get(`${match.source_id}:${match.path}`) ?? 0) >= MAX_MATCHES_PER_FILE
}

// 매치 목록은 소스→문서 순서로 연속 배치되므로(api/search.py가 소스별로 순회하며
// extend), 같은 (source_id, path)의 마지막 항목 뒤에만 "더 있음"을 표시한다.
function isLastInGroup(match: SearchMatch, index: number): boolean {
  const next = search.results.value[index + 1]
  return !next || next.source_id !== match.source_id || next.path !== match.path
}

function moveActive(delta: number) {
  const len = search.results.value.length
  if (!len) return
  search.activeIndex.value = (search.activeIndex.value + delta + len) % len
}

function selectResult(match: SearchMatch) {
  openInActivePane(match.source_id, match.path)
  reveal(match.source_id, match.path, match.line_number)
  close()
}

function selectActive() {
  const match = search.results.value[search.activeIndex.value]
  if (match) selectResult(match)
}

function close() {
  search.close()
}

watch(
  () => search.isOpen.value,
  (isOpen) => {
    if (isOpen) nextTick(() => inputRef.value?.focus())
  }
)

// FR-001: 화면 어디서든 Cmd+K(macOS)/Ctrl+K(Windows·Linux)로 검색을 열고 닫는다.
onKeyStroke('k', (e) => {
  if (!(e.metaKey || e.ctrlKey)) return
  e.preventDefault()
  if (search.isOpen.value) close()
  else search.open()
})

// FR-011: Esc는 팔레트가 열려 있을 때만 닫으며, 닫는 행위 자체는 패널 상태를 바꾸지 않는다.
onKeyStroke('Escape', () => {
  if (search.isOpen.value) close()
})
</script>
