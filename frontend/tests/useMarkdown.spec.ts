import { describe, it, expect } from 'vitest'
import DOMPurify from 'dompurify'
import { useMarkdown } from '../src/composables/useMarkdown'

describe('useMarkdown', () => {
  it('renders heading permalink anchors and code copy buttons that survive DOMPurify sanitization', () => {
    const { render } = useMarkdown()
    const src = ['## 제목', '', '```js', 'console.log("hi")', '```'].join('\n')

    const html = render(src)
    const sanitized = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })

    expect(sanitized).toContain('class="header-anchor"')
    expect(sanitized).toContain('class="code-copy-btn"')
    expect(sanitized).toContain('aria-label="Copy code"')
  })

  it('renders one line-number span per source line, alongside the highlighted <pre>', () => {
    const { render } = useMarkdown()
    const src = ['```js', 'const a = 1', 'const b = 2', 'console.log(a + b)', '```'].join('\n')

    const html = render(src)
    const sanitized = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
    const container = document.createElement('div')
    container.innerHTML = sanitized

    const numbers = container.querySelectorAll('.code-line-numbers span')
    expect(Array.from(numbers).map((el) => el.textContent)).toEqual(['1', '2', '3'])
    expect(container.querySelector('.code-block-body pre.hljs code')).not.toBeNull()
  })

  it('renders a mermaid fence as a raw source div plus a hidden <code> for copying, not a highlighted <pre>', () => {
    const { render } = useMarkdown()
    const src = ['```mermaid', 'graph TD', '  A --> B', '```'].join('\n')

    const html = render(src)
    const sanitized = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
    const container = document.createElement('div')
    container.innerHTML = sanitized

    const block = container.querySelector('.mermaid-block')
    expect(block).not.toBeNull()
    expect(block?.querySelector('pre.hljs')).toBeNull()
    expect(block?.querySelector('.mermaid')?.textContent).toBe('graph TD\n  A --> B')
    expect(block?.querySelector('code[hidden]')?.textContent).toBe('graph TD\n  A --> B')
  })
})
