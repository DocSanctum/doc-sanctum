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
  highlight(code, lang) {
    const highlighted = lang && hljs.getLanguage(lang)
      ? hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
      : hljs.highlightAuto(code).value
    const copyCode = i18n.global.t('viewer.markdown.copyCode')
    const copy = i18n.global.t('common.copy')
    return `<div class="code-block"><button type="button" class="code-copy-btn" aria-label="${copyCode}">${copy}</button><pre class="hljs"><code>${highlighted}</code></pre></div>`
  },
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
