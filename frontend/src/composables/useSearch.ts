import { ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../services/api'
import type { SearchMatch, SearchWarning } from '../types'

// macOS uses ⌘K, Windows/Linux uses Ctrl+K — shared by the search button
// tooltip and the palette hint text (App.vue, CommandPalette.vue). The
// platform never changes during a session, so compute it once at module load.
const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
export const searchShortcutLabel = isMac ? '⌘K' : 'Ctrl+K'

// Module-scope singleton state — same pattern as usePanes.ts/useTreeReveal.ts.
// The search-open button (App.vue) and the palette itself (CommandPalette.vue)
// live in different component trees, so the search session state
// (data-model.md SearchSession) is kept as shared global state.
const isOpen = ref(false)
const query = ref('')
const results = ref<SearchMatch[]>([])
const warnings = ref<SearchWarning[]>([])
const loading = ref(false)
const activeIndex = ref(0)

// Tokenized so a slow, older request can't overwrite results from a newer one.
let requestToken = 0

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

const debouncedRunSearch = useDebounceFn(runSearch, 250)

export function useSearch() {
  function setQuery(value: string) {
    query.value = value
    activeIndex.value = 0
    debouncedRunSearch(value)
  }

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    query.value = ''
    results.value = []
    warnings.value = []
    activeIndex.value = 0
    requestToken++
  }

  return { isOpen, query, results, warnings, loading, activeIndex, setQuery, open, close }
}
