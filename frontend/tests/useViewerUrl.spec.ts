import { describe, it, expect, beforeEach } from 'vitest'
import { useViewerUrl } from '../src/composables/useViewerUrl'

describe('useViewerUrl', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    const { setLocation, setHeadingId } = useViewerUrl()
    setLocation(null, null)
    setHeadingId(null)
  })

  it('has no source/file/heading by default', () => {
    const { getSourceId, getFilePath, getHeadingId } = useViewerUrl()
    expect(getSourceId()).toBeNull()
    expect(getFilePath()).toBeNull()
    expect(getHeadingId()).toBeNull()
  })

  it('syncs source/file to the URL query params', () => {
    const { getSourceId, getFilePath, setLocation } = useViewerUrl()

    setLocation('src-2', 'docs/readme.md')

    expect(getSourceId()).toBe('src-2')
    expect(getFilePath()).toBe('docs/readme.md')
  })

  it('syncs heading id to the URL hash via replaceState', () => {
    const { getHeadingId, setHeadingId } = useViewerUrl()

    setHeadingId('overview')
    expect(getHeadingId()).toBe('overview')
    expect(window.location.hash).toBe('#overview')

    setHeadingId(null)
    expect(getHeadingId()).toBeNull()
  })

  it('builds a permalink URL with source/file query params and an encoded heading hash', () => {
    const { buildPermalink } = useViewerUrl()

    const url = buildPermalink('src-1', 'guide/setup.md', '설치 가이드')
    const parsed = new URL(url)

    expect(parsed.searchParams.get('source')).toBe('src-1')
    expect(parsed.searchParams.get('file')).toBe('guide/setup.md')
    expect(parsed.hash).toBe(`#${encodeURIComponent('설치 가이드')}`)
  })
})
