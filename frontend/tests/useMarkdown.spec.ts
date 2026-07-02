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
    expect(sanitized).toContain('aria-label="코드 복사"')
  })
})
