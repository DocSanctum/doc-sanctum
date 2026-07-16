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

  it('renders one .code-line row per source line, each pairing a number with its own code content', () => {
    const { render } = useMarkdown()
    const src = ['```js', 'const a = 1', 'const b = 2', 'console.log(a + b)', '```'].join('\n')

    const html = render(src)
    const sanitized = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
    const container = document.createElement('div')
    container.innerHTML = sanitized

    const rows = container.querySelectorAll('.code-block-body .code-line')
    expect(rows.length).toBe(3)
    expect(Array.from(rows).map((row) => row.querySelector('.code-line-number')?.textContent)).toEqual([
      '1',
      '2',
      '3',
    ])
    // The number and its code sit in the same row element, so there is no
    // separate gutter/pre pair whose line counts could ever drift apart.
    expect(Array.from(rows).map((row) => row.querySelector('.code-line-content')?.textContent)).toEqual([
      'const a = 1',
      'const b = 2',
      'console.log(a + b)',
    ])
    // A hidden <code> carries the plain, newline-joined source for the copy
    // button, since concatenating the per-line spans' textContent wouldn't
    // reproduce the newlines between them.
    expect(container.querySelector('.code-block > code[hidden]')?.textContent).toBe(
      'const a = 1\nconst b = 2\nconsole.log(a + b)'
    )
  })

  it('splits a highlight.js span that opens and closes across multiple source lines without breaking either line', () => {
    // Regression guard for splitHighlightedLines: a multi-line block comment
    // is highlighted by hljs as one <span class="hljs-comment"> wrapping both
    // lines' text (including the "\n" between them). Splitting on that raw
    // "\n" would leave the first line's <span> unclosed and the second
    // line's text un-highlighted; the row-splitting must close and reopen it
    // at the line boundary instead.
    const { render } = useMarkdown()
    const src = ['```js', '/* first', 'second */', 'const a = 1', '```'].join('\n')

    const html = render(src)
    const sanitized = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
    const container = document.createElement('div')
    container.innerHTML = sanitized

    const rows = container.querySelectorAll('.code-block-body .code-line')
    expect(rows.length).toBe(3)
    expect(rows[0].querySelector('.code-line-content .hljs-comment')).not.toBeNull()
    expect(rows[1].querySelector('.code-line-content .hljs-comment')).not.toBeNull()
    expect(
      Array.from(rows)
        .map((row) => row.querySelector('.code-line-content')?.textContent)
        .join('\n')
    ).toBe('/* first\nsecond */\nconst a = 1')
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
