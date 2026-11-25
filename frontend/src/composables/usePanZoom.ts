import { ref, computed, type Ref } from 'vue'

export interface Transform {
  x: number
  y: number
  scale: number
}

export interface Size {
  width: number
  height: number
}

export const MIN_SCALE = 0.1
export const MAX_SCALE = 8

export function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale))
}

// Centers the content in the viewport at the largest scale that fits, never
// enlarging past maxFit so small raster images stay sharp.
export function fitTransform(content: Size, viewport: Size, padding = 24, maxFit = 1): Transform {
  if (!content.width || !content.height) return { x: 0, y: 0, scale: 1 }
  const scale = clampScale(
    Math.min(
      (viewport.width - padding * 2) / content.width,
      (viewport.height - padding * 2) / content.height,
      maxFit
    )
  )
  return {
    x: (viewport.width - content.width * scale) / 2,
    y: (viewport.height - content.height * scale) / 2,
    scale,
  }
}

// Scales around a viewport point so whatever is under that point stays put.
export function zoomAt(t: Transform, nextScale: number, px: number, py: number): Transform {
  const scale = clampScale(nextScale)
  const ratio = scale / t.scale
  return { x: px - (px - t.x) * ratio, y: py - (py - t.y) * ratio, scale }
}

// Drives wheel, drag and pinch zooming for a viewport element whose content
// is positioned with the returned CSS transform.
export function usePanZoom(viewport: Ref<HTMLElement | null>, maxFit: Ref<number>) {
  const transform = ref<Transform>({ x: 0, y: 0, scale: 1 })
  let contentSize: Size = { width: 0, height: 0 }
  const pointers = new Map<number, { x: number; y: number }>()
  let pinchDistance = 0

  const style = computed(() => ({
    transform: `translate(${transform.value.x}px, ${transform.value.y}px) scale(${transform.value.scale})`,
  }))
  const percent = computed(() => Math.round(transform.value.scale * 100))

  function viewportSize(): Size {
    const rect = viewport.value?.getBoundingClientRect()
    return { width: rect?.width ?? 0, height: rect?.height ?? 0 }
  }

  function localPoint(clientX: number, clientY: number) {
    const rect = viewport.value?.getBoundingClientRect()
    return { x: clientX - (rect?.left ?? 0), y: clientY - (rect?.top ?? 0) }
  }

  function setContentSize(size: Size) {
    contentSize = size
    fit()
  }

  function fit() {
    transform.value = fitTransform(contentSize, viewportSize(), 24, maxFit.value)
  }

  function zoomBy(factor: number) {
    const { width, height } = viewportSize()
    transform.value = zoomAt(transform.value, transform.value.scale * factor, width / 2, height / 2)
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault()
    // Trackpad pinches arrive as ctrl+wheel with small deltas, so they get a
    // stronger factor than mouse wheel notches.
    const factor = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015))
    const p = localPoint(e.clientX, e.clientY)
    transform.value = zoomAt(transform.value, transform.value.scale * factor, p.x, p.y)
  }

  function onPointerDown(e: PointerEvent) {
    viewport.value?.setPointerCapture?.(e.pointerId)
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size === 2) pinchDistance = currentPinchDistance()
  }

  function currentPinchDistance(): number {
    const [a, b] = [...pointers.values()]
    return Math.hypot(a.x - b.x, a.y - b.y)
  }

  function onPointerMove(e: PointerEvent) {
    const prev = pointers.get(e.pointerId)
    if (!prev) return
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size === 1) {
      const t = transform.value
      transform.value = { ...t, x: t.x + e.clientX - prev.x, y: t.y + e.clientY - prev.y }
      return
    }
    if (pointers.size === 2 && pinchDistance > 0) {
      const distance = currentPinchDistance()
      const [a, b] = [...pointers.values()]
      const mid = localPoint((a.x + b.x) / 2, (a.y + b.y) / 2)
      transform.value = zoomAt(transform.value, transform.value.scale * (distance / pinchDistance), mid.x, mid.y)
      pinchDistance = distance
    }
  }

  function onPointerUp(e: PointerEvent) {
    pointers.delete(e.pointerId)
    pinchDistance = pointers.size === 2 ? currentPinchDistance() : 0
  }

  return { transform, style, percent, setContentSize, fit, zoomBy, onWheel, onPointerDown, onPointerMove, onPointerUp }
}
