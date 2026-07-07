import { ref } from 'vue'

export interface RevealTarget {
  sourceId: string
  filePath: string
  lineNumber: number
}

// 모듈 스코프 싱글턴 상태 — useTreeReveal.ts와 동일한 패턴.
// CommandPalette(모달)와 활성 패널의 MarkdownViewer는 서로 다른 컴포넌트
// 트리이므로 "이 줄로 스크롤해줘" 신호를 전역 공유 상태로 전달한다.
//
// 대상 문서(sourceId/filePath)까지 함께 실어 보내는 이유: openInActivePane()
// 직후 reveal()을 호출하면, 문서가 막 새로 열리는 경우 MarkdownViewer가
// 아직 마운트되기 전에 revealToken이 이미 증가해 있을 수 있다(TreeNode.vue의
// reveal-token 레이스와 동일한 문제). 라인 번호만 들고 있으면 "이 토큰을 이미
// 처리했는지" 여부만으로는 그 신호가 자신이 지금 표시 중인 문서를 향한 것인지
// 구분할 수 없다. 대신 대상 문서를 명시해두면, 마운트 시점이 언제든 상관없이
// "지금 내가 보여주는 문서가 이 reveal의 대상과 같은가"만 비교하면 되어 레이스가
// 사라진다.
const revealTarget = ref<RevealTarget | null>(null)
const revealToken = ref(0)

export function useSearchReveal() {
  function reveal(sourceId: string, filePath: string, lineNumber: number) {
    revealTarget.value = { sourceId, filePath, lineNumber }
    revealToken.value++
  }

  return { revealTarget, revealToken, reveal }
}
