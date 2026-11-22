import { describe, it, expect } from 'vitest'
import { resolveDocPath, parseInternalDocLink, isExternalUrl } from '../src/utils/docLinks'

describe('resolveDocPath', () => {
  it('resolves relative to the current document directory', () => {
    expect(resolveDocPath('guide/intro.md', 'images/arch.png')).toBe('guide/images/arch.png')
    expect(resolveDocPath('guide/intro.md', './images/arch.png')).toBe('guide/images/arch.png')
    expect(resolveDocPath('intro.md', 'arch.png')).toBe('arch.png')
  })

  it('normalizes parent segments and treats a leading slash as the source root', () => {
    expect(resolveDocPath('a/b/c.md', '../img/x.png')).toBe('a/img/x.png')
    expect(resolveDocPath('a/b/c.md', '/assets/x.png')).toBe('assets/x.png')
  })

  it('decodes percent-encoded segments and drops query and fragment', () => {
    expect(resolveDocPath('doc.md', 'my%20image.png?raw=1#top')).toBe('my image.png')
  })

  it('rejects references that escape the source root or are external', () => {
    expect(resolveDocPath('doc.md', '../secret.png')).toBeNull()
    expect(resolveDocPath('doc.md', 'https://example.com/a.png')).toBeNull()
    expect(resolveDocPath('doc.md', 'data:image/png;base64,AAAA')).toBeNull()
    expect(resolveDocPath('doc.md', '//cdn.example.com/a.png')).toBeNull()
    expect(resolveDocPath('doc.md', '#heading')).toBeNull()
  })
})

describe('parseInternalDocLink', () => {
  it('keeps the heading fragment of a markdown link', () => {
    expect(parseInternalDocLink('guide/intro.md', 'setup.md#install-steps')).toEqual({
      path: 'guide/setup.md',
      headingId: 'install-steps',
    })
  })

  it('accepts .markdown and uppercase extensions', () => {
    expect(parseInternalDocLink('a.md', 'b.markdown')?.path).toBe('b.markdown')
    expect(parseInternalDocLink('a.md', 'README.MD')?.path).toBe('README.MD')
  })

  it('keeps an encoded heading as-is to match markdown-it-anchor ids', () => {
    expect(parseInternalDocLink('a.md', 'b.md#%EC%84%A4%EC%B9%98')?.headingId).toBe(
      '%EC%84%A4%EC%B9%98'
    )
  })

  it('ignores non-markdown, external, and in-page links', () => {
    expect(parseInternalDocLink('a.md', 'report.pdf')).toBeNull()
    expect(parseInternalDocLink('a.md', 'https://x.com/b.md')).toBeNull()
    expect(parseInternalDocLink('a.md', '#local')).toBeNull()
  })
})

describe('isExternalUrl', () => {
  it('detects schemes and protocol-relative urls', () => {
    expect(isExternalUrl('mailto:a@b.c')).toBe(true)
    expect(isExternalUrl('//host/x')).toBe(true)
    expect(isExternalUrl('docs/a.md')).toBe(false)
  })
})
