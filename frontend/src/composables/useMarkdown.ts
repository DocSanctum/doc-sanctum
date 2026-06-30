import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import anchor from 'markdown-it-anchor'
import footnote from 'markdown-it-footnote'
import abbr from 'markdown-it-abbr'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(code, lang) {
    const highlighted = lang && hljs.getLanguage(lang)
      ? hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
      : hljs.highlightAuto(code).value
    return `<pre class="hljs"><code>${highlighted}</code></pre>`
  },
})
  .use(taskLists, { enabled: true })
  .use(anchor, { permalink: anchor.permalink.headerLink() })
  .use(footnote)
  .use(abbr)

export function useMarkdown() {
  function render(src: string): string {
    return md.render(src)
  }
  return { render }
}
