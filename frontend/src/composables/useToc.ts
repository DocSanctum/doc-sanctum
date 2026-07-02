import { ref, nextTick, onBeforeUnmount, type Ref } from 'vue'

export interface TocEntry {
  id: string
  text: string
  level: number
}

export function useToc(contentRef: Ref<HTMLElement | null | undefined>) {
  const entries = ref<TocEntry[]>([])
  const activeId = ref<string | null>(null)
  let observer: IntersectionObserver | null = null
  const visibleIds = new Set<string>()

  function disconnect() {
    observer?.disconnect()
    observer = null
    visibleIds.clear()
  }

  function headingText(heading: HTMLElement): string {
    const clone = heading.cloneNode(true) as HTMLElement
    clone.querySelectorAll('.header-anchor').forEach((el) => el.remove())
    return clone.textContent?.trim() ?? ''
  }

  async function refresh(preferredActiveId?: string | null) {
    disconnect()
    entries.value = []
    activeId.value = null
    await nextTick()

    const root = contentRef.value
    if (!root) return

    const headings = Array.from(root.querySelectorAll('h1, h2, h3, h4, h5, h6')) as HTMLElement[]
    const withIds = headings.filter((h) => h.id)
    if (withIds.length < 2) return

    entries.value = withIds.map((h) => ({
      id: h.id,
      text: headingText(h),
      level: Number(h.tagName[1]),
    }))
    // 딥링크(퍼머링크)로 진입한 경우 실제로 스크롤된 헤딩을 초기 활성 상태로
    // 사용한다. IntersectionObserver의 첫 콜백이 도착하기 전까지의 짧은 순간
    // 동안 잘못된(첫 헤딩) 활성 표시가 깜빡이는 것을 막는다 — 관찰 자체는
    // 항상 이 함수 호출 전에 이미 스크롤이 끝난 뒤 시작되므로, 콜백이 도착하면
    // 어차피 같은 값으로 다시 확인될 뿐이다.
    const preferred = preferredActiveId && entries.value.some((e) => e.id === preferredActiveId)
      ? preferredActiveId
      : entries.value[0].id
    activeId.value = preferred

    observer = new IntersectionObserver(
      (observed) => {
        for (const entry of observed) {
          const id = (entry.target as HTMLElement).id
          if (entry.isIntersecting) visibleIds.add(id)
          else visibleIds.delete(id)
        }
        const firstVisible = entries.value.find((e) => visibleIds.has(e.id))
        if (firstVisible) activeId.value = firstVisible.id
      },
      { rootMargin: '0px 0px -80% 0px', threshold: 0 }
    )
    withIds.forEach((h) => observer!.observe(h))
  }

  onBeforeUnmount(disconnect)

  return { entries, activeId, refresh }
}
