import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useLocale } from '../src/composables/useLocale'
import { api } from '../src/services/api'

vi.mock('../src/services/api', () => ({
  api: { getLocale: vi.fn() },
}))

// Node's own (unconfigured, non-functional) global `localStorage` shadows
// jsdom's in this test environment, so stub an in-memory Storage per test
// instead of relying on the ambient global.
function createMemoryStorage(): Storage {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => {
      store.clear()
    },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size
    },
  } as Storage
}

describe('useLocale', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createMemoryStorage())
    vi.mocked(api.getLocale).mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the stored locale and skips the backend call when one is already saved', async () => {
    localStorage.setItem('ds-locale', 'ko')
    const { initLocale, locale } = useLocale()

    await initLocale()

    expect(locale.value).toBe('ko')
    expect(api.getLocale).not.toHaveBeenCalled()
  })

  it('applies the backend-detected locale when nothing is stored yet', async () => {
    vi.mocked(api.getLocale).mockResolvedValue({ locale: 'ko' })
    const { initLocale, locale } = useLocale()

    await initLocale()

    expect(locale.value).toBe('ko')
    expect(localStorage.getItem('ds-locale')).toBe('ko')
  })

  it('falls back to the browser language when the backend cannot determine a country', async () => {
    vi.mocked(api.getLocale).mockResolvedValue({ locale: 'unknown' })
    vi.stubGlobal('navigator', { language: 'ko-KR' })
    const { initLocale, locale } = useLocale()

    await initLocale()

    expect(locale.value).toBe('ko')
  })

  it('falls back to the browser language when the backend call fails', async () => {
    vi.mocked(api.getLocale).mockRejectedValue(new Error('network error'))
    vi.stubGlobal('navigator', { language: 'en-US' })
    const { initLocale, locale } = useLocale()

    await initLocale()

    expect(locale.value).toBe('en')
  })

  it('defaults to English when the browser language is neither stored nor Korean', async () => {
    vi.mocked(api.getLocale).mockResolvedValue({ locale: 'unknown' })
    vi.stubGlobal('navigator', { language: 'fr-FR' })
    const { initLocale, locale } = useLocale()

    await initLocale()

    expect(locale.value).toBe('en')
  })

  it('setLocale overrides the auto-detected value and persists the manual choice', async () => {
    vi.mocked(api.getLocale).mockResolvedValue({ locale: 'en' })
    const { initLocale, setLocale, locale } = useLocale()

    await initLocale()
    expect(locale.value).toBe('en')

    setLocale('ko')

    expect(locale.value).toBe('ko')
    expect(localStorage.getItem('ds-locale')).toBe('ko')

    // A later init (e.g. a fresh page load) must honor the manual choice
    // over whatever the backend would auto-detect.
    vi.mocked(api.getLocale).mockClear()
    await initLocale()
    expect(locale.value).toBe('ko')
    expect(api.getLocale).not.toHaveBeenCalled()
  })
})
