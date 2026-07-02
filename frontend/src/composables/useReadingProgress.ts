import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useScroll } from '@vueuse/core'

const BACK_TO_TOP_THRESHOLD = 400

export function useReadingProgress(container: MaybeRefOrGetter<HTMLElement | null | undefined>) {
  const { y, arrivedState } = useScroll(container, { throttle: 100 })

  const ratio = computed(() => {
    const el = toValue(container)
    if (!el) return 0
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
