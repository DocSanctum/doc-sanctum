import { ref } from 'vue'

export interface RevealTarget {
  sourceId: string
  filePath: string
  lineNumber: number
}

// Module-scope singleton state — same pattern as useTreeReveal.ts.
// CommandPalette (a modal) and the active pane's MarkdownViewer live in
// different component trees, so the "scroll to this line" signal is
// delivered via shared global state.
//
// Why the target document (sourceId/filePath) is carried along as well:
// calling reveal() right after openInActivePane() can increment revealToken
// before MarkdownViewer even mounts, when the document is being opened for
// the first time (the same race useTreeReveal.ts's reveal-token handles).
// With only a line number, "have I already handled this token" can't tell
// whether the signal is even meant for the document this instance currently
// shows. Carrying the target document instead means the check is simply
// "does the document I'm showing right now match this reveal's target",
// regardless of when the component happens to mount — no race.
const revealTarget = ref<RevealTarget | null>(null)
const revealToken = ref(0)

export function useSearchReveal() {
  function reveal(sourceId: string, filePath: string, lineNumber: number) {
    revealTarget.value = { sourceId, filePath, lineNumber }
    revealToken.value++
  }

  return { revealTarget, revealToken, reveal }
}
