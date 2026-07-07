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
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1.5 px-0.5">
          {{ t('search.shortcutHint', { shortcut: searchShortcutLabel }) }}
        </p>
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
              :pane-options="paneOptions"
              @select="selectResult(match)"
              @hover="search.activeIndex.value = index"
              @open-in-pane="openInPane(match, $event)"
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
import { useSearch, searchShortcutLabel } from '../../composables/useSearch'
import { useSearchReveal } from '../../composables/useSearchReveal'
import { usePanes } from '../../composables/usePanes'
import { useSources } from '../../composables/useSources'
import SearchResultItem from './SearchResultItem.vue'
import type { SearchMatch, PaneId } from '../../types'

// Must match MAX_MATCHES_PER_FILE in backend/app/mcp/tools/search_documents.py
// (FR-012) — the API response has no explicit "truncated" flag, so we infer
// it by checking whether a document's match count hit this cap.
const MAX_MATCHES_PER_FILE = 10

const { t } = useI18n()
const search = useSearch()
const { reveal } = useSearchReveal()
const { panes, colorOf, openInActivePane, setPaneDocument, setActivePane } = usePanes()
const { sourcesQuery } = useSources()

const inputRef = ref<HTMLInputElement | null>(null)

const noSources = computed(() => (sourcesQuery.data.value?.length ?? 0) === 0)

// Only show the "open in this pane" icons next to a result when 2+ panes
// are open (see SearchResultItem.vue) — with a single pane it's no
// different from just clicking the row.
const paneOptions = computed(() => panes.value.map((p) => ({ id: p.id, color: colorOf(p.id) })))

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

// Matches are laid out in contiguous source→document runs (api/search.py
// iterates per source and extends the list), so only show "more matches"
// after the last item of a given (source_id, path) run.
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

// Clicking a pane icon next to a result opens it directly in the pane the
// user picked, not the active one. MarkdownViewer's highlight only reacts in
// the active pane (so it's unambiguous which pane reacts when the same
// document is open in both), so also switch the chosen pane to active to
// guarantee the highlight is visible there.
function openInPane(match: SearchMatch, paneId: PaneId) {
  setPaneDocument(paneId, match.source_id, match.path)
  setActivePane(paneId)
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

// FR-001: open/close search from anywhere on screen via Cmd+K (macOS) / Ctrl+K (Windows·Linux).
onKeyStroke('k', (e) => {
  if (!(e.metaKey || e.ctrlKey)) return
  e.preventDefault()
  if (search.isOpen.value) close()
  else search.open()
})

// FR-011: Esc only closes the palette while it's open; closing itself never changes pane state.
onKeyStroke('Escape', () => {
  if (search.isOpen.value) close()
})
</script>
