import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import CommandPalette from '../src/components/CommandPalette/CommandPalette.vue'
import { useSearch } from '../src/composables/useSearch'
import { usePanes } from '../src/composables/usePanes'
import { useSearchReveal } from '../src/composables/useSearchReveal'
import { api } from '../src/services/api'
import type { Source, SearchMatch } from '../src/types'

vi.mock('../src/services/api', () => ({
  api: { getSources: vi.fn(), search: vi.fn() },
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

function resetSingletons() {
  window.history.replaceState(null, '', '/')
  const { panes, closePane, setPaneDocument } = usePanes()
  if (panes.value.length > 1) closePane(panes.value[1].id)
  setPaneDocument(1, null, null)
  useSearch().close()
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
})
