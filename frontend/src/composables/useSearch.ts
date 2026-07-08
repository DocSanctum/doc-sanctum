import { ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../services/api'
import type { SearchMatch, SearchWarning, SearchMode, SemanticMatch } from '../types'

// Shown together rather than switched by platform, so the shortcut hint
// (search button tooltip and palette hint text — App.vue, CommandPalette.vue)
// works whether the user reads it on macOS or Windows/Linux.
export const searchShortcutLabel = '⌘K / Ctrl+K'

// Module-scope singleton state — same pattern as usePanes.ts/useTreeReveal.ts.
// The search-open button (App.vue) and the palette itself (CommandPalette.vue)
// live in different component trees, so the search session state
// (data-model.md SearchSession) is kept as shared global state.
const isOpen = ref(false)
const query = ref('')
// FR-010: the last-picked mode persists across opening/closing the palette
// within the same session, so it's kept alongside the rest of this
// module-scope singleton state rather than reset in close().
const mode = ref<SearchMode>('keyword')
const results = ref<SearchMatch[]>([])
const warnings = ref<SearchWarning[]>([])
const loading = ref(false)
const semanticResults = ref<SemanticMatch[]>([])
const semanticWarnings = ref<SearchWarning[]>([])
const semanticLoading = ref(false)
const activeIndex = ref(0)

// Tokenized so a slow, older request can't overwrite results from a newer one.
let requestToken = 0
let semanticRequestToken = 0

async function runSearch(q: string) {
  const trimmed = q.trim()
  // FR-013: don't send a request at all when the query is empty or whitespace-only.
  if (!trimmed) {
    requestToken++
    results.value = []
    warnings.value = []
    loading.value = false
    return
  }
  const token = ++requestToken
  loading.value = true
  try {
    const res = await api.search(trimmed)
    if (token !== requestToken) return
    results.value = res.matches
    warnings.value = res.warnings
  } catch {
    if (token !== requestToken) return
    results.value = []
    warnings.value = []
  } finally {
    if (token === requestToken) loading.value = false
  }
}

async function runSemanticSearch(q: string) {
  const trimmed = q.trim()
  // FR-011: same rule as keyword mode — no request for an empty/whitespace-only query.
  if (!trimmed) {
    semanticRequestToken++
    semanticResults.value = []
    semanticWarnings.value = []
    semanticLoading.value = false
    return
  }
  const token = ++semanticRequestToken
  semanticLoading.value = true
  try {
    const res = await api.semanticSearch(trimmed)
    if (token !== semanticRequestToken) return
    semanticResults.value = res.results
    semanticWarnings.value = res.warnings
  } catch {
    if (token !== semanticRequestToken) return
    semanticResults.value = []
    semanticWarnings.value = []
  } finally {
    if (token === semanticRequestToken) semanticLoading.value = false
  }
}

const debouncedRunSearch = useDebounceFn(runSearch, 250)
const debouncedRunSemanticSearch = useDebounceFn(runSemanticSearch, 250)

export function useSearch() {
  function setQuery(value: string) {
    query.value = value
    activeIndex.value = 0
    if (mode.value === 'keyword') debouncedRunSearch(value)
    else debouncedRunSemanticSearch(value)
  }

  // FR-009: switching modes keeps the current query text and re-runs the
  // search under the newly selected mode's logic right away — this is a
  // discrete tab click, not typing, so it isn't debounced like setQuery().
  function setMode(next: SearchMode) {
    if (mode.value === next) return
    mode.value = next
    activeIndex.value = 0
    if (next === 'keyword') runSearch(query.value)
    else runSemanticSearch(query.value)
  }

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    query.value = ''
    results.value = []
    warnings.value = []
    semanticResults.value = []
    semanticWarnings.value = []
    activeIndex.value = 0
    requestToken++
    semanticRequestToken++
  }

  return {
    isOpen,
    query,
    mode,
    results,
    warnings,
    loading,
    semanticResults,
    semanticWarnings,
    semanticLoading,
    activeIndex,
    setQuery,
    setMode,
    open,
    close,
  }
}
