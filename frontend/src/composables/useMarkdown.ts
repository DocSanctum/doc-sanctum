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
// directly avoids both: a single <pre> per code block, with data-line kept.
md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx]
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : ''
  const langName = info.split(/\s+/)[0] ?? ''
  const highlighted = langName && hljs.getLanguage(langName)
    ? hljs.highlight(token.content, { language: langName, ignoreIllegals: true }).value
    : hljs.highlightAuto(token.content).value
  const copyCode = i18n.global.t('viewer.markdown.copyCode')
  const copy = i18n.global.t('common.copy')
  const dataLine = token.attrGet('data-line')
  const dataLineAttr = dataLine ? ` data-line="${md.utils.escapeHtml(dataLine)}"` : ''
  return `<pre class="hljs code-block"${dataLineAttr}><button type="button" class="code-copy-btn" aria-label="${copyCode}">${copy}</button><code>${highlighted}</code></pre>`
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
