import DOMPurify from 'dompurify'

export type ImageSrcResolver = (src: string) => string | null

// A dedicated instance, so these hooks never touch other DOMPurify callers
// such as the mermaid fullscreen SVG sanitizer.
const purifier = DOMPurify(window)
const TEXT_ALIGN_ONLY = /^\s*text-align:\s*(left|right|center)\s*;?\s*$/i
let activeResolver: ImageSrcResolver | null = null

// Inline styles could restyle or overlay the app, so only the table
// alignment markdown-it itself emits is kept.
purifier.addHook('uponSanitizeAttribute', (_node, data) => {
  if (data.attrName === 'style' && !TEXT_ALIGN_ONLY.test(data.attrValue)) data.keepAttr = false
})

// Runs on the inert parsing document, so a relative src is rewritten
// before the browser ever requests it.
purifier.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName !== 'IMG') return
  const src = node.getAttribute('src')
  const resolved = src && activeResolver ? activeResolver(src) : null
  if (resolved) node.setAttribute('src', resolved)
  node.setAttribute('loading', 'lazy')
})

// Sanitizes rendered Markdown, which may contain raw HTML from the document.
export function sanitizeMarkdownHtml(html: string, resolveImageSrc?: ImageSrcResolver): string {
  activeResolver = resolveImageSrc ?? null
  try {
    return purifier.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['style', 'form', 'textarea', 'select', 'option'],
    })
  } finally {
    activeResolver = null
  }
}
