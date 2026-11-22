import type MarkdownIt from 'markdown-it'
import type StateCore from 'markdown-it/lib/rules_core/state_core.mjs'

export type AlertKind = 'note' | 'tip' | 'important' | 'warning' | 'caution'

// GitHub's five alert types, plus the Obsidian callout names folded into them.
const KIND_BY_NAME: Record<string, AlertKind> = {
  note: 'note', info: 'note', todo: 'note', abstract: 'note', summary: 'note', tldr: 'note',
  example: 'note', quote: 'note', cite: 'note',
  tip: 'tip', hint: 'tip', success: 'tip', check: 'tip', done: 'tip',
  important: 'important', question: 'important', help: 'important', faq: 'important',
  warning: 'warning', attention: 'warning',
  caution: 'caution', danger: 'caution', error: 'caution', bug: 'caution', failure: 'caution',
  fail: 'caution', missing: 'caution',
}

const MARKER = /^\[!([A-Za-z]+)\]([+-]?)[ \t]*(.*)$/

function findClose(tokens: StateCore['tokens'], openIdx: number): number {
  let depth = 0
  for (let j = openIdx; j < tokens.length; j++) {
    if (tokens[j].type === 'blockquote_open') depth++
    else if (tokens[j].type === 'blockquote_close' && --depth === 0) return j
  }
  return -1
}

function alertsRule(state: StateCore): void {
  const tokens = state.tokens
  for (let i = 0; i < tokens.length; i++) {
    const open = tokens[i]
    const inline = tokens[i + 2]
    if (open.type !== 'blockquote_open' || tokens[i + 1]?.type !== 'paragraph_open') continue
    if (inline?.type !== 'inline') continue
    const [firstLine, ...rest] = inline.content.split('\n')
    const match = MARKER.exec(firstLine)
    const closeIdx = findClose(tokens, i)
    if (!match || closeIdx === -1) continue

    const name = match[1].toLowerCase()
    const fold = match[2]
    const kind = KIND_BY_NAME[name] ?? 'note'
    open.attrJoin('class', `markdown-alert markdown-alert-${kind}`)
    if (fold) {
      open.tag = 'details'
      tokens[closeIdx].tag = 'details'
      if (fold === '+') open.attrSet('open', '')
    }
    const title = new state.Token('alert_title', fold ? 'summary' : 'p', 0)
    title.content = match[3].trim() || name.charAt(0).toUpperCase() + name.slice(1)

    // The marker line becomes the title; drop its paragraph if nothing else was in it.
    if (rest.length > 0) {
      inline.content = rest.join('\n')
      tokens.splice(i + 1, 0, title)
    } else {
      tokens.splice(i + 1, 3, title)
    }
  }
}

// Renders "> [!NOTE]" style alerts and Obsidian callouts, where "[!note]-"
// and "[!note]+" become collapsible blocks that start closed or open.
export function alertsPlugin(md: MarkdownIt): void {
  md.core.ruler.before('inline', 'alerts', alertsRule)
  md.renderer.rules.alert_title = (tokens, idx) => {
    const token = tokens[idx]
    return `<${token.tag} class="markdown-alert-title">${md.utils.escapeHtml(token.content)}</${token.tag}>`
  }
}
