import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { i18n } from '../src/i18n'
import ZoomLightbox from '../src/components/Viewer/ZoomLightbox.vue'

const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200"></svg>'

// jsdom has no PointerEvent, so a MouseEvent carrying a pointerId stands in.
function pointer(type: string, pointerId: number, clientX = 0, clientY = 0): Event {
  const event = new MouseEvent(type, { clientX, clientY, bubbles: true })
  Object.defineProperty(event, 'pointerId', { value: pointerId })
  return event
}

function contentTransform(): string {
  return (document.querySelector('.zoom-content') as HTMLElement).style.transform
}

describe('ZoomLightbox', () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      x: 0, y: 0, left: 0, top: 0, width: 848, height: 648, right: 848, bottom: 648, toJSON: () => ({}),
    } as DOMRect)
  })
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  async function mountSvg() {
    const wrapper = mount(ZoomLightbox, { props: { svg: SVG }, global: { plugins: [i18n] }, attachTo: document.body })
    await flushPromises()
    return wrapper
  }

  it('fits a diagram to the viewport, enlarging vectors up to 2x', async () => {
    await mountSvg()
    expect(contentTransform()).toBe('translate(24px, 124px) scale(2)')
    expect(document.querySelector('.zoom-percent')?.textContent).toBe('200%')
  })

  it('zooms with the toolbar and resets with fit', async () => {
    await mountSvg()
    const buttons = document.querySelectorAll<HTMLButtonElement>('.zoom-toolbar button')
    buttons[0].click()
    await flushPromises()
    expect(document.querySelector('.zoom-percent')?.textContent).toBe('160%')
    buttons[2].click()
    await flushPromises()
    expect(document.querySelector('.zoom-percent')?.textContent).toBe('200%')
  })

  it('zooms on wheel and pans on drag', async () => {
    await mountSvg()
    const viewport = document.querySelector('.zoom-viewport') as HTMLElement
    viewport.dispatchEvent(new WheelEvent('wheel', { deltaY: 200, clientX: 424, clientY: 324, cancelable: true }))
    await flushPromises()
    expect(Number(document.querySelector('.zoom-percent')?.textContent?.replace('%', ''))).toBeLessThan(200)

    const before = contentTransform()
    viewport.dispatchEvent(pointer('pointerdown', 1, 100, 100))
    viewport.dispatchEvent(pointer('pointermove', 1, 130, 90))
    viewport.dispatchEvent(pointer('pointerup', 1))
    await flushPromises()
    expect(contentTransform()).not.toBe(before)
  })

  it('closes on Escape and on the close button', async () => {
    const wrapper = await mountSvg()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    document.querySelector<HTMLButtonElement>('.zoom-close')!.click()
    expect(wrapper.emitted('close')).toHaveLength(2)
  })
})
