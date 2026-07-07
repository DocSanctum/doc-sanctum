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
    return md.render(src)
  }
  return { render }
}
