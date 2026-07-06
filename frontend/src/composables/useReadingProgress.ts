import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useScroll, useResizeObserver } from '@vueuse/core'

const BACK_TO_TOP_THRESHOLD = 400
// Safari's native rubber-band/momentum scrolling can settle several pixels short
// of the true scrollable max (worse than Chrome, which has no elastic overscroll),
// so vueuse's own 1px arrivedState.bottom threshold isn't always enough there —
// widen it via useScroll's offset so the bar still reaches 100% at the true bottom.
const BOTTOM_ARRIVAL_TOLERANCE_PX = 12

export function useReadingProgress(container: MaybeRefOrGetter<HTMLElement | null | undefined>) {
  const { y, arrivedState, measure } = useScroll(container, {
    throttle: 100,
    offset: { bottom: BOTTOM_ARRIVAL_TOLERANCE_PX },
  })

  // arrivedState is only recomputed on 'scroll' events, but the container's
  // content can change height without one ever firing — e.g. the "loading…"
  // placeholder is replaced by the real (much taller) document once it
  // finishes fetching. With the tolerance above, that placeholder's height
  // can sit within a few px of clientHeight and get mistaken for "already at
  // the bottom", a false reading that then never corrects itself until the
  // user scrolls. Re-measure on every size change so it stays accurate.
  useResizeObserver(container, () => measure())

  const ratio = computed(() => {
    const el = toValue(container)
    if (!el) return 0
    // Sub-pixel rounding and scroll-event throttling can leave y.value just
    // short of the theoretical max (scrollHeight - clientHeight), making the
    // ratio appear to fall a hair short of 100% even at the true bottom.
    // Trust useScroll's own arrivedState.bottom and snap straight to 100%
    // whenever it fires.
    if (arrivedState.bottom) return 1
    const scrollable = el.scrollHeight - el.clientHeight
    return scrollable > 0 ? Math.min(1, Math.max(0, y.value / scrollable)) : 0
  })

  const showBackToTop = computed(() => y.value > BACK_TO_TOP_THRESHOLD)
  const atTop = computed(() => arrivedState.top)

  function scrollToTop() {
    toValue(container)?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function reset() {
    toValue(container)?.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }

  return { ratio, showBackToTop, atTop, scrollToTop, reset }
}
