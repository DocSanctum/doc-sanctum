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
    // 검색 결과에서 특정 원문 줄로 스크롤하려면(008-search) 렌더링된 블록
    // 요소가 원문의 몇 번째 줄에서 시작하는지 알아야 한다. markdown-it은
    // 블록 토큰마다 원문 라인 범위(token.map)를 이미 갖고 있으므로, 별도
    // 파서 없이 md.render() 한 번 호출 대신 parse → data-line 속성 부여 →
    // renderer.render 3단계로 나눠 이 정보를 DOM에 실어 보낸다. inline
    // 토큰은 부모 블록 태그 안에서 렌더링될 뿐 자신의 태그가 없으므로 제외한다.
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
