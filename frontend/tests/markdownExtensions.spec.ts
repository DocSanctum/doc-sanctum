import { describe, it, expect } from 'vitest'
import { useMarkdown } from '../src/composables/useMarkdown'
import { sanitizeMarkdownHtml } from '../src/utils/sanitizeMarkdown'
import { extractFrontMatter, toFrontMatterView } from '../src/utils/frontMatter'

function renderToDom(src: string, resolve?: (s: string) => string | null): HTMLElement {
  const container = document.createElement('div')
  container.innerHTML = sanitizeMarkdownHtml(useMarkdown().render(src), resolve)
  return container
}

describe('alerts', () => {
  it('turns a GitHub alert into a titled block without the marker text', () => {
    const dom = renderToDom('> [!WARNING]\n> Back up first.')
    const alert = dom.querySelector('blockquote.markdown-alert.markdown-alert-warning')
    expect(alert?.querySelector('.markdown-alert-title')?.textContent).toBe('Warning')
    expect(alert?.textContent).not.toContain('[!WARNING]')
    expect(alert?.querySelector('p:not(.markdown-alert-title)')?.textContent).toBe('Back up first.')
  })

  it('maps Obsidian callout names and keeps a custom title', () => {
    const dom = renderToDom('> [!danger] Do not run in prod\n> It drops tables.')
    const alert = dom.querySelector('.markdown-alert-caution')
    expect(alert?.querySelector('.markdown-alert-title')?.textContent).toBe('Do not run in prod')
  })

  it('renders foldable callouts as details that start closed or open', () => {
    const closed = renderToDom('> [!info]- More\n> hidden body').querySelector('details.markdown-alert')
    expect(closed?.hasAttribute('open')).toBe(false)
    expect(closed?.querySelector('summary')?.textContent).toBe('More')
    const open = renderToDom('> [!tip]+\n> shown').querySelector('details.markdown-alert')
    expect(open?.hasAttribute('open')).toBe(true)
  })

  it('leaves ordinary blockquotes alone', () => {
    const dom = renderToDom('> just a quote')
    expect(dom.querySelector('blockquote')?.classList.contains('markdown-alert')).toBe(false)
  })
})

describe('raw HTML', () => {
  it('keeps common README markup', () => {
    const dom = renderToDom('<details><summary>More</summary>\n\nBody\n\n</details>\n\nPress <kbd>Ctrl</kbd><br>done')
    expect(dom.querySelector('details > summary')?.textContent).toBe('More')
    expect(dom.querySelector('kbd')?.textContent).toBe('Ctrl')
    expect(dom.querySelector('br')).not.toBeNull()
  })

  it('removes scripts, handlers, style tags, forms and free-form inline styles', () => {
    const dom = renderToDom(
      '<script>alert(1)</script><img src="x.png" onerror="alert(1)">' +
        '<style>body{display:none}</style><form><input name="q"></form>' +
        '<div style="position:fixed;inset:0">overlay</div>'
    )
    expect(dom.querySelector('script, style, form')).toBeNull()
    expect(dom.querySelector('img')?.hasAttribute('onerror')).toBe(false)
    expect(dom.querySelector('div')?.hasAttribute('style')).toBe(false)
  })

  it('keeps table column alignment styles', () => {
    const dom = renderToDom('| a |\n|--:|\n| 1 |')
    expect(dom.querySelector('td')?.getAttribute('style')).toBe('text-align:right')
  })

  it('rewrites markdown and raw HTML image sources once, before the browser sees them', () => {
    const dom = renderToDom(
      '![a](img/a.png)\n\n<img src="img/b.png" width="120">\n\n![c](https://x.com/c.png)',
      (src) => (src.startsWith('http') ? null : `/asset/${src}`)
    )
    const srcs = Array.from(dom.querySelectorAll('img')).map((i) => i.getAttribute('src'))
    expect(srcs).toEqual(['/asset/img/a.png', '/asset/img/b.png', 'https://x.com/c.png'])
    expect(dom.querySelector('img[width="120"]')?.getAttribute('loading')).toBe('lazy')
  })
})

describe('front matter', () => {
  const doc = '---\ntitle: Plan\ntags: [infra, "#ops"]\ndate: 2026-01-02\n---\n# Heading\n'

  it('strips the block but keeps later lines at their original line numbers', () => {
    const { data, body } = extractFrontMatter(doc)
    expect(data?.title).toBe('Plan')
    expect(body.split('\n')[5]).toBe('# Heading')
    const html = useMarkdown().render(body)
    expect(html).toContain('data-line="6"')
    expect(html).not.toContain('title: Plan')
  })

  it('shapes tags as chips and other keys as text', () => {
    const view = toFrontMatterView(extractFrontMatter(doc).data!)
    expect(view.tags).toEqual(['infra', 'ops'])
    expect(view.fields).toEqual([
      { key: 'title', value: 'Plan' },
      { key: 'date', value: '2026-01-02' },
    ])
  })

  it('leaves documents without valid YAML front matter unchanged', () => {
    const thematicBreak = '---\nnot: [valid\n---\ntext'
    expect(extractFrontMatter(thematicBreak).body).toBe(thematicBreak)
    expect(extractFrontMatter('# Just text\n---\n').data).toBeNull()
    expect(extractFrontMatter('---\n- a\n- b\n---\n').data).toBeNull()
  })
})

describe('code blocks', () => {
  it('labels a named language with its display name', () => {
    const dom = renderToDom('```js\nconst a = 1\n```')
    expect(dom.querySelector('.code-block .code-lang')?.textContent).toBe('JavaScript')
  })

  it('does not label auto-detected code', () => {
    expect(renderToDom('```\nplain\n```').querySelector('.code-lang')).toBeNull()
  })

  it('gives mermaid blocks a loading label for the placeholder', () => {
    const dom = renderToDom('```mermaid\ngraph TD; A-->B\n```')
    expect(dom.querySelector('.mermaid')?.getAttribute('data-loading-label')).toBe('Rendering diagram…')
  })
})
