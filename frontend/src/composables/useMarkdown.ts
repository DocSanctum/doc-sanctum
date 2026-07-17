import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import anchor from 'markdown-it-anchor'
import footnote from 'markdown-it-footnote'
import abbr from 'markdown-it-abbr'
import hljs from 'highlight.js'
import { i18n } from '../i18n'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
})
  .use(taskLists, { enabled: true })
  .use(anchor, {
    permalink: anchor.permalink.linkInsideHeader({
      class: 'header-anchor',
      symbol: '#',
      placement: 'after',
      ariaHidden: true,
    }),
  })
  .use(footnote)
  .use(abbr)

// markdown-it's default fence renderer wraps whatever `options.highlight`
// returns in its own `<pre><code>` unless that string starts with literal
// `<pre` — and even then it drops the token's own attrs (our data-line,
// used to scroll a search result into view). Overriding the fence rule
// directly avoids both: a single wrapper per code block, with data-line kept.
//
// The wrapper is a <div class="code-block">, not a <pre>, since mermaid
// blocks need a plain <div class="mermaid"> (mermaid.js's own convention)
// instead of a highlighted <pre><code>. A hidden <code> holding the raw
// source is always included so the existing copy-button handler (which
// does `.closest('.code-block').querySelector('code')`) works unchanged
// for both cases.

// highlight.js returns one flat HTML string where a <span class="hljs-...">
// can open on one source line and close several lines later (multi-line
// comments/strings), so splitting on raw "\n" would leave those spans
// unbalanced per line. This walks the markup instead, splitting only on
// text-node newlines, and reopens whatever tags are still on the stack at
// the start of the next line — keeping each returned line self-contained,
// valid HTML. The line count always matches the source's line count, since
// hljs never adds or removes "\n" characters, only wraps them in spans.
function splitHighlightedLines(html: string): string[] {
  const lines: string[] = []
  const openTags: string[] = []
  let line = ''
  let i = 0
  while (i < html.length) {
    const ch = html[i]
    if (ch === '<') {
      const end = html.indexOf('>', i)
      const tag = html.slice(i, end + 1)
      line += tag
      if (tag.startsWith('</')) openTags.pop()
      else openTags.push(tag)
      i = end + 1
    } else if (ch === '\n') {
      lines.push(line + '</span>'.repeat(openTags.length))
      line = openTags.join('')
      i++
    } else {
      const nextTag = html.indexOf('<', i)
      const nextNewline = html.indexOf('\n', i)
      const candidates = [nextTag, nextNewline].filter((n) => n !== -1)
      const stop = candidates.length ? Math.min(...candidates) : html.length
      line += html.slice(i, stop)
      i = stop
    }
  }
  lines.push(line)
  return lines
}

md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx]
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : ''
  const langName = info.split(/\s+/)[0] ?? ''
  const copyCode = i18n.global.t('viewer.markdown.copyCode')
  const copy = i18n.global.t('common.copy')
  const dataLine = token.attrGet('data-line')
  const dataLineAttr = dataLine ? ` data-line="${md.utils.escapeHtml(dataLine)}"` : ''
  const copyBtn = `<button type="button" class="code-copy-btn" aria-label="${copyCode}">${copy}</button>`
  const rawSource = token.content.replace(/\n$/, '')

  if (langName === 'mermaid') {
    const escaped = md.utils.escapeHtml(rawSource)
    const viewFullscreen = i18n.global.t('viewer.markdown.viewFullscreen')
    const fullscreenBtn = `<button type="button" class="mermaid-fullscreen-btn" aria-label="${viewFullscreen}" title="${viewFullscreen}">${viewFullscreen}</button>`
    // Both buttons share one flex wrapper (instead of each being
    // independently absolutely-positioned like a lone .code-copy-btn is for
    // plain code blocks) so they space themselves out regardless of label
    // length/locale, rather than a hardcoded `right` offset drifting out of
    // sync between the two.
    // The diagram itself is wrapped in .mermaid-block-scroll, a second,
    // inner overflow-x container — mermaid-block-actions sits outside that
    // wrapper (in the non-scrolling parent) so the buttons stay pinned to
    // the corner instead of panning away with the diagram on horizontal
    // scroll, the way .code-block-body already keeps line numbers/content
    // scrolling separately from the plain code-block's own copy button.
    return `<div class="code-block mermaid-block"${dataLineAttr}><div class="mermaid-block-actions">${copyBtn}${fullscreenBtn}</div><code hidden>${escaped}</code><div class="mermaid-block-scroll"><div class="mermaid">${escaped}</div></div></div>`
  }

  // Use rawSource (trailing "\n" already stripped), not token.content — hljs
  // preserves that trailing newline as an extra blank line, which would add
  // one more row than the source actually has.
  const highlighted = langName && hljs.getLanguage(langName)
    ? hljs.highlight(rawSource, { language: langName, ignoreIllegals: true }).value
    : hljs.highlightAuto(rawSource).value
  // Each source line becomes its own row — number and code content as
  // flex siblings within *that* row — instead of two independently laid out
  // columns (a numbers gutter vs. a single <pre> blob) kept in sync only by
  // matching CSS. Pairing them per row makes the browser lay out each row's
  // number and content together, so they can't drift apart from rounding,
  // font substitution, or zoom — there's nothing left to keep in sync.
  // A hidden <code> carries the plain raw source for the copy button, since
  // .textContent across many per-line <span>s would otherwise join lines
  // without the newlines between them.
  const rows = splitHighlightedLines(highlighted)
    .map(
      (lineHtml, i) =>
        `<div class="code-line">` +
        `<span class="code-line-number" aria-hidden="true">${i + 1}</span>` +
        `<span class="code-line-content">${lineHtml}</span>` +
        `</div>`
    )
    .join('')
  return (
    `<div class="code-block"${dataLineAttr}>${copyBtn}` +
    `<code hidden>${md.utils.escapeHtml(rawSource)}</code>` +
    `<div class="code-block-body hljs">${rows}</div>` +
    `</div>`
  )
}

export function useMarkdown() {
  function render(src: string): string {
    // Scrolling to a specific source line from a search result (008-search)
    // requires knowing which source line a rendered block element starts at.
    // markdown-it already tracks each block token's source line range
    // (token.map), so instead of a single md.render() call, split it into
    // parse → attach data-line attributes → renderer.render so that
    // information rides along into the DOM. Inline tokens are excluded since
    // they render inside their parent block's tag and have no tag of their own.
    const env = {}
    const tokens = md.parse(src, env)
    for (const token of tokens) {
      if (token.map && token.nesting >= 0 && token.type !== 'inline') {
        token.attrSet('data-line', String(token.map[0] + 1))
      }
    }
    return md.renderer.render(tokens, md.options, env)
  }
  return { render }
}
