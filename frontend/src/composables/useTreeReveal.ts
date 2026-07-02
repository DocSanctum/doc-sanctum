import { ref } from 'vue'

// 모듈 스코프 싱글턴 상태 — useViewerSettings.ts와 동일한 패턴.
// Breadcrumb(뷰어 영역)과 FileTree/TreeNode(사이드바)는 서로 다른 컴포넌트
// 트리이므로 전역 공유 상태로 "이 경로를 펼쳐서 보여줘" 신호를 전달한다.
const revealPath = ref<string | null>(null)
const revealToken = ref(0)

export function useTreeReveal() {
  function reveal(path: string) {
    revealPath.value = path
    revealToken.value++
  }

  return { revealPath, revealToken, reveal }
}
