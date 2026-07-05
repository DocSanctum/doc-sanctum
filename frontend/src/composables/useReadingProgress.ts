import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useScroll } from '@vueuse/core'

const BACK_TO_TOP_THRESHOLD = 400

export function useReadingProgress(container: MaybeRefOrGetter<HTMLElement | null | undefined>) {
  const { y, arrivedState } = useScroll(container, { throttle: 100 })

  const ratio = computed(() => {
    const el = toValue(container)
    if (!el) return 0
    // 서브픽셀 반올림/스크롤 이벤트 쓰로틀 지연 때문에 y.value가 이론적
    // 최댓값(scrollHeight - clientHeight)에 정확히 도달하지 못하는 경우가 있어,
    // 맨 끝까지 스크롤해도 진행률이 100%를 살짝 못 채우는 것처럼 보였다.
    // useScroll이 이미 1px 오차로 판정하는 arrivedState.bottom을 그대로 신뢰해
    // 바닥에 도달하면 무조건 100%로 스냅한다.
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
