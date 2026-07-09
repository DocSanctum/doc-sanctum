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
          autocomplete="off"
          data-1p-ignore
          data-lpignore="true"
          data-form-type="other"
          :value="search.query.value"
          :placeholder="t('search.placeholder')"
          :aria-label="t('search.ariaLabel')"
          @input="search.setQuery(($event.target as HTMLInputElement).value)"
          @keydown.down.prevent="moveActive(1)"
          @keydown.up.prevent="moveActive(-1)"
          @keydown.enter.prevent="selectActive"
          @keydown.tab.prevent="toggleMode"
        />
        <div class="flex items-center gap-1 mt-2">
          <button
            type="button"
            class="text-xs px-2 py-1 rounded transition-colors"
            :class="search.mode.value === 'keyword'
              ? 'bg-blue-600 text-white'
              : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'"
            @click="search.setMode('keyword')"
          >{{ t('search.modeKeyword') }}</button>
          <button
            type="button"
            class="text-xs px-2 py-1 rounded transition-colors"
            :class="search.mode.value === 'semantic'
              ? 'bg-blue-600 text-white'
              : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'"
            @click="search.setMode('semantic')"
          >{{ t('search.modeSemantic') }}</button>
        </div>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1.5 px-0.5">
          {{ t('search.shortcutHint', { shortcut: searchShortcutLabel }) }} · {{ t('search.tabSwitchHint', { mode: nextModeLabel }) }}
        </p>
      </div>
      <div class="overflow-y-auto flex-1 p-1 viewer-pane-scroll">
        <p v-if="noSources" class="text-sm text-gray-400 px-3 py-4">{{ t('search.noSources') }}</p>

        <template v-else-if="isLoading">
          <p class="text-sm text-gray-400 px-3 py-4">{{ t('search.loading') }}</p>
        </template>

        <template v-else-if="search.mode.value === 'keyword'">
          <p
            v-if="hasQuery && search.results.value.length === 0"
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
          <div v-if="search.warnings.value.length" class="border-t border-gray-200 dark:border-gray-700 mt-1 pt-1">
            <p v-for="(w, i) in search.warnings.value" :key="i" class="text-xs text-amber-500 px-3 py-1">
              {{ t('search.warning', { name: w.source_name ?? '', message: w.message }) }}
            </p>
          </div>
        </template>

        <template v-else>
          <!-- FR-007: distinct from "no results" — the engine itself being
               unavailable is a different situation from a query that simply
               has no matching documents. -->
          <p v-if="hasEngineUnavailableWarning" class="text-sm text-amber-500 px-3 py-4">
            {{ t('search.engineUnavailable') }}
          </p>
          <p
            v-else-if="hasQuery && search.semanticResults.value.length === 0"
            class="text-sm text-gray-400 px-3 py-4"
          >{{ t('search.noResults') }}</p>
          <template v-for="(match, index) in search.semanticResults.value" :key="`${match.source_id}:${match.path}:${match.chunk_index}`">
            <SemanticResultItem
              :match="match"
              :active="index === search.activeIndex.value"
              :pane-options="paneOptions"
              @select="selectSemanticResult(match)"
              @hover="search.activeIndex.value = index"
              @open-in-pane="openSemanticInPane(match, $event)"
            />
          </template>
        </template>
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
import SemanticResultItem from './SemanticResultItem.vue'
import type { SearchMatch, SemanticMatch, PaneId } from '../../types'

// Must match MAX_MATCHES_PER_FILE in backend/app/keywordindex/client.py
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
const hasQuery = computed(() => search.query.value.trim().length > 0)
const isLoading = computed(() =>
  search.mode.value === 'keyword' ? search.loading.value : search.semanticLoading.value
)
// Semantic search never surfaces per-source failure warnings (research.md #3
// — no live network call happens at query time, unlike keyword search's
// GitHub-rate-limit-style failures), so this is the only warning shape to
// check for in semantic mode.
const hasEngineUnavailableWarning = computed(() =>
  search.semanticWarnings.value.some((w) => w.reason === 'engine_unavailable')
)

// Label of the mode Tab would switch *to*, shown in the hint text below the
// mode tabs so the hint always describes the next press rather than a
// generic "Tab switches mode" message.
const nextModeLabel = computed(() =>
  search.mode.value === 'keyword' ? t('search.modeSemantic') : t('search.modeKeyword')
)

function toggleMode() {
  search.setMode(search.mode.value === 'keyword' ? 'semantic' : 'keyword')
}

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

function activeResultsLength(): number {
  return search.mode.value === 'keyword'
    ? search.results.value.length
    : search.semanticResults.value.length
}

function moveActive(delta: number) {
  const len = activeResultsLength()
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

// Semantic results are chunk-level excerpts, not exact source lines, so
// unlike selectResult()/openInPane() above there's no reveal() call here —
// the document just opens without a line-level scroll/highlight (Assumptions).
function selectSemanticResult(match: SemanticMatch) {
  openInActivePane(match.source_id, match.path)
  close()
}

function openSemanticInPane(match: SemanticMatch, paneId: PaneId) {
  setPaneDocument(paneId, match.source_id, match.path)
  setActivePane(paneId)
  close()
}

function selectActive() {
  if (search.mode.value === 'keyword') {
    const match = search.results.value[search.activeIndex.value]
    if (match) selectResult(match)
  } else {
    const match = search.semanticResults.value[search.activeIndex.value]
    if (match) selectSemanticResult(match)
  }
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
