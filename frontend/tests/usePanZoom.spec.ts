import { describe, it, expect } from 'vitest'
import { clampScale, fitTransform, zoomAt, MAX_SCALE, MIN_SCALE } from '../src/composables/usePanZoom'

describe('fitTransform', () => {
  it('shrinks large content to fit and centers it', () => {
    const t = fitTransform({ width: 2000, height: 1000 }, { width: 1048, height: 800 }, 24)
    expect(t.scale).toBe(0.5)
    expect(t.x).toBe(24)
    expect(t.y).toBe(150)
  })

  it('never enlarges past maxFit', () => {
    expect(fitTransform({ width: 100, height: 50 }, { width: 1000, height: 800 }, 24, 1).scale).toBe(1)
    expect(fitTransform({ width: 100, height: 50 }, { width: 1000, height: 800 }, 24, 2).scale).toBe(2)
  })

  it('falls back to identity for unmeasured content', () => {
    expect(fitTransform({ width: 0, height: 0 }, { width: 800, height: 600 })).toEqual({ x: 0, y: 0, scale: 1 })
  })
})

describe('zoomAt', () => {
  it('keeps the point under the cursor fixed', () => {
    const before = { x: 10, y: 20, scale: 1 }
    const after = zoomAt(before, 2, 110, 70)
    const contentX = (110 - before.x) / before.scale
    expect(after.x + contentX * after.scale).toBeCloseTo(110)
    expect(after.scale).toBe(2)
  })

  it('clamps the scale to its limits', () => {
    expect(zoomAt({ x: 0, y: 0, scale: 1 }, 1000, 0, 0).scale).toBe(MAX_SCALE)
    expect(clampScale(0)).toBe(MIN_SCALE)
  })
})
