import { describe, it, expect, beforeEach } from 'vitest'
import { usePanes } from '../src/composables/usePanes'

describe('usePanes', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    const { panes, closePane, setPaneDocument } = usePanes()
    if (panes.value.length > 1) closePane(panes.value[1].id)
    setPaneDocument(1, null, null)
  })

  it('starts with a single empty pane, active', () => {
    const { panes, activePaneId } = usePanes()
    expect(panes.value).toHaveLength(1)
    expect(panes.value[0]).toMatchObject({ id: 1, sourceId: null, filePath: null })
    expect(activePaneId.value).toBe(1)
  })

  it('opens a document in the active pane without affecting other panes', () => {
    const { panes, addPane, setActivePane, openInActivePane } = usePanes()

    openInActivePane('src-1', 'a.md')
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'a.md' })

    addPane()
    setActivePane(2)
    openInActivePane('src-2', 'b.md')

    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'a.md' })
    expect(panes.value[1]).toMatchObject({ sourceId: 'src-2', filePath: 'b.md' })
  })

  it('switching a document in one pane does not touch the other pane', () => {
    const { panes, addPane, setActivePane, openInActivePane } = usePanes()

    openInActivePane('src-1', 'a.md')
    addPane()
    setActivePane(2)
    openInActivePane('src-2', 'b.md')

    setActivePane(1)
    openInActivePane('src-1', 'c.md')

    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'c.md' })
    expect(panes.value[1]).toMatchObject({ sourceId: 'src-2', filePath: 'b.md' })
  })

  it('does not add more than 2 panes', () => {
    const { panes, addPane, canAddPane } = usePanes()

    expect(canAddPane()).toBe(true)
    addPane()
    expect(panes.value).toHaveLength(2)
    expect(canAddPane()).toBe(false)

    addPane()
    expect(panes.value).toHaveLength(2)
  })

  it('assigns a default color per pane id', () => {
    const { addPane, colorOf } = usePanes()
    addPane()
    expect(colorOf(1)).toBe('blue')
    expect(colorOf(2)).toBe('amber')
  })

  it('lets a pane color be changed, and resets colors to defaults when closing back to one pane', () => {
    const { addPane, colorOf, setPaneColor, closePane } = usePanes()
    addPane()

    setPaneColor(2, 'purple')
    expect(colorOf(2)).toBe('purple')
    expect(colorOf(1)).toBe('blue')

    closePane(2)
    expect(colorOf(1)).toBe('blue')

    addPane()
    expect(colorOf(2)).toBe('amber')
  })

  it('reports every pane a given document is open in', () => {
    const { addPane, setActivePane, openInActivePane, paneMatches } = usePanes()

    openInActivePane('src-1', 'a.md')
    addPane()
    setActivePane(2)
    openInActivePane('src-1', 'a.md')

    expect(paneMatches('src-1', 'a.md')).toEqual([
      { paneId: 1, color: 'blue' },
      { paneId: 2, color: 'amber' },
    ])
    expect(paneMatches('src-1', 'other.md')).toEqual([])
  })

  it('never closes the last remaining pane', () => {
    const { panes, closePane } = usePanes()
    closePane(1)
    expect(panes.value).toHaveLength(1)
  })

  it('closing a pane reassigns the survivor to id 1 with pane-1 color and makes it active', () => {
    const { panes, activePaneId, addPane, setActivePane, openInActivePane, closePane, colorOf } = usePanes()

    openInActivePane('src-1', 'a.md')
    addPane()
    setActivePane(2)
    openInActivePane('src-2', 'b.md')

    closePane(1)

    expect(panes.value).toHaveLength(1)
    expect(panes.value[0]).toMatchObject({ id: 1, sourceId: 'src-2', filePath: 'b.md' })
    expect(colorOf(panes.value[0].id)).toBe('blue')
    expect(activePaneId.value).toBe(1)
  })

  it('allows adding a pane again after closing back down to one', () => {
    const { panes, addPane, closePane, canAddPane } = usePanes()

    addPane()
    closePane(2)
    expect(canAddPane()).toBe(true)

    addPane()
    expect(panes.value).toHaveLength(2)
  })

  it('tracks per-pane visit history and supports going back and forward', () => {
    const { panes, openInActivePane, canGoBack, canGoForward, goBack, goForward } = usePanes()

    expect(canGoBack(1)).toBe(false)
    expect(canGoForward(1)).toBe(false)

    openInActivePane('src-1', 'a.md')
    openInActivePane('src-1', 'b.md')
    openInActivePane('src-1', 'c.md')

    expect(canGoBack(1)).toBe(true)
    expect(canGoForward(1)).toBe(false)

    goBack(1)
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'b.md' })
    expect(canGoBack(1)).toBe(true)
    expect(canGoForward(1)).toBe(true)

    goBack(1)
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'a.md' })
    expect(canGoBack(1)).toBe(false)

    goBack(1) // no-op, already at the start
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'a.md' })

    goForward(1)
    goForward(1)
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'c.md' })
    expect(canGoForward(1)).toBe(false)

    goForward(1) // no-op, already at the end
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'c.md' })
  })

  it('navigating after going back truncates the forward history', () => {
    const { panes, openInActivePane, canGoForward, goBack } = usePanes()

    openInActivePane('src-1', 'a.md')
    openInActivePane('src-1', 'b.md')
    goBack(1)
    expect(canGoForward(1)).toBe(true)

    openInActivePane('src-1', 'c.md')
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'c.md' })
    expect(canGoForward(1)).toBe(false)
  })

  it('keeps each pane history independent', () => {
    const { panes, addPane, setActivePane, openInActivePane, canGoBack, goBack } = usePanes()

    openInActivePane('src-1', 'a.md')
    openInActivePane('src-1', 'b.md')
    addPane()
    setActivePane(2)
    openInActivePane('src-2', 'x.md')
    openInActivePane('src-2', 'y.md')

    expect(canGoBack(1)).toBe(true)
    expect(canGoBack(2)).toBe(true)

    goBack(2)
    expect(panes.value[1]).toMatchObject({ sourceId: 'src-2', filePath: 'x.md' })
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-1', filePath: 'b.md' })
  })

  it('carries the surviving pane history over to slot 1 when closing a pane', () => {
    const { panes, addPane, setActivePane, openInActivePane, closePane, canGoBack, goBack } = usePanes()

    addPane()
    setActivePane(2)
    openInActivePane('src-2', 'x.md')
    openInActivePane('src-2', 'y.md')

    closePane(1)

    expect(canGoBack(1)).toBe(true)
    goBack(1)
    expect(panes.value[0]).toMatchObject({ sourceId: 'src-2', filePath: 'x.md' })
  })
})
