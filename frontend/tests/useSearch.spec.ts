import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSearch } from '../src/composables/useSearch'
import { api } from '../src/services/api'

vi.mock('../src/services/api', () => ({
  api: { search: vi.fn() },
}))

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('useSearch', () => {
  beforeEach(() => {
    vi.mocked(api.search).mockReset()
    useSearch().close()
  })

  it('does not call the API when the query is blank or whitespace-only', async () => {
    const { setQuery } = useSearch()

    setQuery('   ')
    await wait(300)

    expect(api.search).not.toHaveBeenCalled()
  })

  it('debounces input and populates results/warnings from the API response', async () => {
    vi.mocked(api.search).mockResolvedValue({
      query: 'auth',
      matches: [
        { source_id: 's1', source_name: 'docs-a', path: 'a.md', line_number: 3, line: 'auth flow', context: ['auth flow'] },
      ],
      warnings: [{ source_id: 's2', source_name: 'docs-b', message: 'unreachable' }],
    })
    const { setQuery, results, warnings } = useSearch()

    setQuery('a')
    setQuery('au')
    setQuery('auth')
    await wait(300)

    // Only the last input value is called with, not the intermediate ones typed during the debounce.
    expect(api.search).toHaveBeenCalledTimes(1)
    expect(api.search).toHaveBeenCalledWith('auth')
    expect(results.value).toHaveLength(1)
    expect(results.value[0].path).toBe('a.md')
    expect(warnings.value).toHaveLength(1)
  })

  it('resets activeIndex to 0 whenever the query changes', async () => {
    vi.mocked(api.search).mockResolvedValue({
      query: 'x',
      matches: [
        { source_id: 's1', source_name: 'docs-a', path: 'a.md', line_number: 1, line: 'x', context: ['x'] },
        { source_id: 's1', source_name: 'docs-a', path: 'b.md', line_number: 1, line: 'x', context: ['x'] },
      ],
      warnings: [],
    })
    const { setQuery, activeIndex } = useSearch()

    setQuery('x')
    await wait(300)
    activeIndex.value = 1

    setQuery('xy')
    expect(activeIndex.value).toBe(0)
  })

  it('close() clears query, results, warnings and closes the palette', async () => {
    vi.mocked(api.search).mockResolvedValue({
      query: 'x',
      matches: [{ source_id: 's1', source_name: 'docs-a', path: 'a.md', line_number: 1, line: 'x', context: ['x'] }],
      warnings: [],
    })
    const { setQuery, close, open, isOpen, query, results } = useSearch()

    open()
    setQuery('x')
    await wait(300)
    expect(results.value).toHaveLength(1)

    close()

    expect(isOpen.value).toBe(false)
    expect(query.value).toBe('')
    expect(results.value).toEqual([])
  })

  it('ignores a stale response that resolves after a newer query was issued', async () => {
    let resolveFirst!: (value: any) => void
    vi.mocked(api.search).mockImplementationOnce(
      () => new Promise((resolve) => { resolveFirst = resolve })
    )
    const { setQuery, results } = useSearch()

    setQuery('first')
    await wait(300) // first request has gone out and is still awaiting a response

    vi.mocked(api.search).mockResolvedValueOnce({
      query: 'second',
      matches: [{ source_id: 's1', source_name: 'docs-a', path: 'second.md', line_number: 1, line: 'x', context: ['x'] }],
      warnings: [],
    })
    setQuery('second')
    await wait(300) // second request has also completed

    // Even if the first request's response arrives late, it must not overwrite the newer result.
    resolveFirst({ query: 'first', matches: [{ source_id: 's1', source_name: 'docs-a', path: 'first.md', line_number: 1, line: 'x', context: ['x'] }], warnings: [] })
    await wait(10)

    expect(results.value).toHaveLength(1)
    expect(results.value[0].path).toBe('second.md')
  })
})
