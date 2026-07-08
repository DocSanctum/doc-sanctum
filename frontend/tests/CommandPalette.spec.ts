import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import CommandPalette from '../src/components/CommandPalette/CommandPalette.vue'
import { useSearch } from '../src/composables/useSearch'
import { usePanes } from '../src/composables/usePanes'
import { useSearchReveal } from '../src/composables/useSearchReveal'
import { api } from '../src/services/api'
import type { Source, SearchMatch, SemanticMatch } from '../src/types'

vi.mock('../src/services/api', () => ({
  api: { getSources: vi.fn(), search: vi.fn(), semanticSearch: vi.fn() },
}))

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function makeSource(id: string): Source {
  return {
    id,
    name: id,
    type: 'local',
    path: `/${id}`,
    polling_interval_seconds: null,
    created_at: '',
    status: 'active',
    error_message: null,
    icon: null,
  }
}

function makeMatch(overrides: Partial<SearchMatch> = {}): SearchMatch {
  return {
    source_id: 's1',
    source_name: 'docs-a',
    path: 'a.md',
    line_number: 3,
    line: 'keyword line',
    context: ['before', 'keyword line', 'after'],
    ...overrides,
  }
}

function makeSemanticMatch(overrides: Partial<SemanticMatch> = {}): SemanticMatch {
  return {
    source_id: 's1',
    source_name: 'docs-a',
    path: 'a.md',
    chunk_index: 0,
    score: 0.8,
    excerpt: 'OAuth2 login flow excerpt',
    ...overrides,
  }
}

function resetSingletons() {
  window.history.replaceState(null, '', '/')
  const { panes, closePane, setPaneDocument } = usePanes()
  if (panes.value.length > 1) closePane(panes.value[1].id)
  setPaneDocument(1, null, null)
  useSearch().close()
  // mode intentionally persists across close() (FR-010), so it must be
  // reset explicitly between tests to avoid leaking state.
  useSearch().setMode('keyword')
}

function mountPalette(): VueWrapper {
  return mount(CommandPalette, {
    global: { plugins: [[VueQueryPlugin, { queryClient: new QueryClient() }]] },
  })
}

describe('CommandPalette', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.mocked(api.getSources).mockReset()
    vi.mocked(api.search).mockReset()
    vi.mocked(api.semanticSearch).mockReset()
    resetSingletons()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  it('shows the "no sources" state when nothing is registered', async () => {
    vi.mocked(api.getSources).mockResolvedValue([])
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    expect(wrapper.text()).toContain('No registered sources to search')
  })

  it('shows the "no results" state for a query with no matches', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'x', matches: [], warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('nomatch')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('No results found')
  })

  it('renders matches and shows a "more matches" indicator when a document hits the per-file cap', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    const cappedMatches = Array.from({ length: 10 }, (_, i) => makeMatch({ line_number: i + 1 }))
    vi.mocked(api.search).mockResolvedValue({ query: 'kw', matches: cappedMatches, warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('More matches in this document')
  })

  it('shows warnings from partially failed sources', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({
      query: 'kw',
      matches: [],
      warnings: [{ source_id: 's2', source_name: 'docs-b', message: 'unreachable' }],
    })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('docs-b')
    expect(wrapper.text()).toContain('unreachable')
  })

  it('clicking a result opens it in the active pane and scrolls/reveals the matched line, then closes', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'kw', matches: [makeMatch()], warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    const { revealToken } = useSearchReveal()
    const tokenBefore = revealToken.value

    await wrapper.find('.search-result-row').trigger('click')

    const { panes } = usePanes()
    expect(panes.value[0]).toMatchObject({ sourceId: 's1', filePath: 'a.md' })
    expect(revealToken.value).toBe(tokenBefore + 1)
    expect(useSearch().isOpen.value).toBe(false)
  })

  it('clicking a pane icon opens the result in that specific pane, regardless of which pane is active', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'kw', matches: [makeMatch()], warnings: [] })

    const { addPane, setActivePane, panes, activePaneId } = usePanes()
    addPane()
    setActivePane(1) // active pane is 1, but the result is opened via pane 2's icon.

    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    const paneButtons = wrapper.findAll('.search-result-row button')
    expect(paneButtons).toHaveLength(2) // 2 panes means 2 icons
    await paneButtons[1].trigger('click')

    expect(panes.value[0]).toMatchObject({ sourceId: null, filePath: null }) // pane 1 untouched
    expect(panes.value[1]).toMatchObject({ sourceId: 's1', filePath: 'a.md' })
    expect(activePaneId.value).toBe(2) // the chosen pane also becomes active
    expect(useSearch().isOpen.value).toBe(false)
  })

  it('does not show per-pane icons when only one pane is open', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'kw', matches: [makeMatch()], warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    expect(wrapper.findAll('.search-result-row button')).toHaveLength(0)
  })

  it('ArrowDown then Enter selects the second result', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({
      query: 'kw',
      matches: [makeMatch({ path: 'a.md' }), makeMatch({ path: 'b.md' })],
      warnings: [],
    })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('kw')
    await wait(300)
    await flushPromises()

    const input = wrapper.find('input')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })

    const { panes } = usePanes()
    expect(panes.value[0]).toMatchObject({ sourceId: 's1', filePath: 'b.md' })
  })

  it('Escape closes the palette without changing pane state', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'kw', matches: [makeMatch()], warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    const { panes, openInActivePane } = usePanes()
    openInActivePane('existing', 'already-open.md')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(useSearch().isOpen.value).toBe(false)
    expect(panes.value[0]).toMatchObject({ sourceId: 'existing', filePath: 'already-open.md' })
  })

  it('global Cmd+K toggles the palette open and closed', async () => {
    vi.mocked(api.getSources).mockResolvedValue([])
    wrapper = mountPalette()
    await flushPromises()
    expect(useSearch().isOpen.value).toBe(false)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))
    await flushPromises()
    expect(useSearch().isOpen.value).toBe(true)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))
    await flushPromises()
    expect(useSearch().isOpen.value).toBe(false)
  })

  // US1: mode tabs + semantic result list (T012)
  it('renders keyword/semantic mode tabs and switches the visible result list, keeping the query', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'auth', matches: [makeMatch()], warnings: [] })
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [makeSemanticMatch()],
      warnings: [],
    })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()
    expect(wrapper.text()).toContain('keyword line')

    const semanticTab = wrapper.findAll('button').find((b) => b.text() === 'Semantic')
    await semanticTab?.trigger('click')
    await flushPromises()

    expect(api.semanticSearch).toHaveBeenCalledWith('auth')
    expect(wrapper.text()).toContain('OAuth2 login flow excerpt')
    expect(wrapper.text()).not.toContain('keyword line')
  })

  it('pressing Tab toggles between keyword and semantic mode, cycling back and forth', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.search).mockResolvedValue({ query: 'auth', matches: [makeMatch()], warnings: [] })
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [makeSemanticMatch()],
      warnings: [],
    })
    wrapper = mountPalette()
    useSearch().open()
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()
    expect(useSearch().mode.value).toBe('keyword')
    expect(wrapper.text()).toContain('keyword line')

    const input = wrapper.find('input')
    await input.trigger('keydown', { key: 'Tab' })
    await flushPromises()
    expect(useSearch().mode.value).toBe('semantic')
    expect(wrapper.text()).toContain('OAuth2 login flow excerpt')

    await input.trigger('keydown', { key: 'Tab' })
    await flushPromises()
    expect(useSearch().mode.value).toBe('keyword')
    expect(wrapper.text()).toContain('keyword line')
  })

  it('shows the "no results" state in semantic mode for a query with no matches', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.semanticSearch).mockResolvedValue({ query: 'x', results: [], warnings: [] })
    wrapper = mountPalette()
    useSearch().open()
    useSearch().setMode('semantic')
    await flushPromises()

    useSearch().setQuery('nomatch')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('No results found')
  })

  it('renders semantic matches with source name, path, and excerpt', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [makeSemanticMatch({ source_name: 'docs-a', path: 'guides/auth.md', excerpt: 'OAuth2 flow...' })],
      warnings: [],
    })
    wrapper = mountPalette()
    useSearch().open()
    useSearch().setMode('semantic')
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('docs-a')
    expect(wrapper.text()).toContain('guides/auth.md')
    expect(wrapper.text()).toContain('OAuth2 flow...')
  })

  // US3: engine-unavailable warning distinct from "no results" (T016)
  it('shows an engine-unavailable warning distinct from "no results" in semantic mode', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [],
      warnings: [{ reason: 'engine_unavailable', message: 'unavailable' }],
    })
    wrapper = mountPalette()
    useSearch().open()
    useSearch().setMode('semantic')
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()

    expect(wrapper.text()).toContain('Semantic search is unavailable right now')
    expect(wrapper.text()).not.toContain('No results found')
  })

  // US2: opening a semantic result in a pane (T014)
  it('clicking a semantic result opens it in the active pane without a line reveal, then closes', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [makeSemanticMatch()],
      warnings: [],
    })
    wrapper = mountPalette()
    useSearch().open()
    useSearch().setMode('semantic')
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()

    const { revealToken } = useSearchReveal()
    const tokenBefore = revealToken.value

    await wrapper.find('.search-result-row').trigger('click')

    const { panes } = usePanes()
    expect(panes.value[0]).toMatchObject({ sourceId: 's1', filePath: 'a.md' })
    // Semantic matches are chunk-level excerpts, not exact source lines, so
    // selecting one never triggers the line-reveal/highlight (Assumptions).
    expect(revealToken.value).toBe(tokenBefore)
    expect(useSearch().isOpen.value).toBe(false)
  })

  it('clicking a pane icon on a semantic result opens it in that specific pane', async () => {
    vi.mocked(api.getSources).mockResolvedValue([makeSource('s1')])
    vi.mocked(api.semanticSearch).mockResolvedValue({
      query: 'auth',
      results: [makeSemanticMatch()],
      warnings: [],
    })

    const { addPane, setActivePane, panes, activePaneId } = usePanes()
    addPane()
    setActivePane(1) // active pane is 1, but the result is opened via pane 2's icon.

    wrapper = mountPalette()
    useSearch().open()
    useSearch().setMode('semantic')
    await flushPromises()

    useSearch().setQuery('auth')
    await wait(300)
    await flushPromises()

    const paneButtons = wrapper.findAll('.search-result-row button')
    expect(paneButtons).toHaveLength(2) // 2 panes means 2 icons
    await paneButtons[1].trigger('click')

    expect(panes.value[0]).toMatchObject({ sourceId: null, filePath: null }) // pane 1 untouched
    expect(panes.value[1]).toMatchObject({ sourceId: 's1', filePath: 'a.md' })
    expect(activePaneId.value).toBe(2) // the chosen pane also becomes active
    expect(useSearch().isOpen.value).toBe(false)
  })
})
