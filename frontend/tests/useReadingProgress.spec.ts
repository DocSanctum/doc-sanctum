import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useReadingProgress } from '../src/composables/useReadingProgress'

function mockScrollableElement(scrollHeight: number, clientHeight: number): HTMLElement {
  const el = document.createElement('div')
  Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true })
  Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true })
  document.body.appendChild(el)
  return el
}

function scrollTo(el: HTMLElement, top: number) {
  el.scrollTop = top
  el.dispatchEvent(new Event('scroll'))
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('useReadingProgress', () => {
  it('computes scroll ratio based on container scroll position', async () => {
    const el = mockScrollableElement(2000, 1000) // scrollable distance = 1000
    const containerRef = ref<HTMLElement | null>(el)
    const { ratio } = useReadingProgress(containerRef)

    scrollTo(el, 500)
    await wait(150)

    expect(ratio.value).toBeCloseTo(0.5)
  })

  it('shows the back-to-top button only past the threshold', async () => {
    const el = mockScrollableElement(3000, 1000)
    const containerRef = ref<HTMLElement | null>(el)
    const { showBackToTop } = useReadingProgress(containerRef)

    scrollTo(el, 100)
    await wait(150)
    expect(showBackToTop.value).toBe(false)

    scrollTo(el, 500)
    await wait(150)
    expect(showBackToTop.value).toBe(true)
  })

  it('snaps ratio to 1 at the bottom even if y falls a sub-pixel fraction short of the scrollable max', async () => {
    const el = mockScrollableElement(2000, 1000) // scrollable distance = 1000
    const containerRef = ref<HTMLElement | null>(el)
    const { ratio } = useReadingProgress(containerRef)

    scrollTo(el, 999.6)
    await wait(150)

    expect(ratio.value).toBe(1)
  })

  it('snaps ratio to 1 when Safari-style rubber-band scrolling settles several pixels short of the max', async () => {
    const el = mockScrollableElement(2000, 1000) // scrollable distance = 1000
    const containerRef = ref<HTMLElement | null>(el)
    const { ratio } = useReadingProgress(containerRef)

    scrollTo(el, 990) // 10px short, beyond a plain 1px threshold
    await wait(150)

    expect(ratio.value).toBe(1)
  })

  it('returns 0 ratio when there is no container', () => {
    const containerRef = ref<HTMLElement | null>(null)
    const { ratio, showBackToTop } = useReadingProgress(containerRef)

    expect(ratio.value).toBe(0)
    expect(showBackToTop.value).toBe(false)
  })
})
