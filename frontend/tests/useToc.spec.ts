import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { useToc } from '../src/composables/useToc'

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', IntersectionObserverMock)
})

function buildContent(html: string): HTMLElement {
  const el = document.createElement('div')
  el.innerHTML = html
  return el
}

describe('useToc', () => {
  it('extracts headings with ids and strips permalink anchor text', async () => {
    const content = buildContent(`
      <h2 id="intro">소개<a class="header-anchor" href="#intro">#</a></h2>
      <p>본문</p>
      <h3 id="detail">세부사항<a class="header-anchor" href="#detail">#</a></h3>
    `)
    const contentRef = ref<HTMLElement | null>(content)
    const { entries, activeId, refresh } = useToc(contentRef)

    await refresh()

    expect(entries.value).toEqual([
      { id: 'intro', text: '소개', level: 2 },
      { id: 'detail', text: '세부사항', level: 3 },
    ])
    expect(activeId.value).toBe('intro')
  })

  it('does not populate entries when fewer than 2 headings have ids', async () => {
    const content = buildContent('<h2 id="only">유일한 헤딩</h2>')
    const contentRef = ref<HTMLElement | null>(content)
    const { entries, activeId, refresh } = useToc(contentRef)

    await refresh()

    expect(entries.value).toEqual([])
    expect(activeId.value).toBeNull()
  })

  it('ignores headings without an id when counting toward the minimum', async () => {
    const content = buildContent(`
      <h2>id 없음</h2>
      <h3 id="withid">id 있음</h3>
    `)
    const contentRef = ref<HTMLElement | null>(content)
    const { entries, refresh } = useToc(contentRef)

    await refresh()

    expect(entries.value).toEqual([])
  })

  it('uses the preferred active id (e.g. from a deep link) instead of defaulting to the first heading', async () => {
    const content = buildContent(`
      <h2 id="intro">소개</h2>
      <h3 id="detail">세부사항</h3>
    `)
    const contentRef = ref<HTMLElement | null>(content)
    const { activeId, refresh } = useToc(contentRef)

    await refresh('detail')

    expect(activeId.value).toBe('detail')
  })

  it('falls back to the first heading when the preferred active id does not exist', async () => {
    const content = buildContent(`
      <h2 id="intro">소개</h2>
      <h3 id="detail">세부사항</h3>
    `)
    const contentRef = ref<HTMLElement | null>(content)
    const { activeId, refresh } = useToc(contentRef)

    await refresh('not-a-real-id')

    expect(activeId.value).toBe('intro')
  })

  it('clears previous entries when refreshed against an empty container', async () => {
    const content = buildContent(`
      <h2 id="a">A</h2>
      <h3 id="b">B</h3>
    `)
    const contentRef = ref<HTMLElement | null>(content)
    const { entries, refresh } = useToc(contentRef)
    await refresh()
    expect(entries.value.length).toBe(2)

    contentRef.value = buildContent('<p>헤딩 없음</p>')
    await refresh()

    expect(entries.value).toEqual([])
  })
})
