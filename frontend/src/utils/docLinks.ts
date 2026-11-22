// Resolves links and image sources written inside a Markdown document
// against that document's own location within its source.

const EXTERNAL_SCHEME = /^[a-z][a-z0-9+.-]*:/i
const MARKDOWN_EXT = /\.(md|markdown)$/i

export function isExternalUrl(href: string): boolean {
  return EXTERNAL_SCHEME.test(href) || href.startsWith('//')
}

function safeDecode(part: string): string {
  try {
    return decodeURIComponent(part)
  } catch {
    return part
  }
}

// Returns a normalized source-relative path, where a leading "/" means the
// source root, or null for external, empty, or root-escaping references.
export function resolveDocPath(currentFile: string, ref: string): string | null {
  const pathPart = ref.split(/[?#]/, 1)[0]
  if (!pathPart || isExternalUrl(ref)) return null
  const base = pathPart.startsWith('/') ? [] : currentFile.split('/').slice(0, -1)
  const segments = [...base]
  for (const raw of pathPart.split('/')) {
    const seg = safeDecode(raw)
    if (seg === '' || seg === '.') continue
    if (seg === '..') {
      if (segments.length === 0) return null
      segments.pop()
      continue
    }
    segments.push(seg)
  }
  return segments.length ? segments.join('/') : null
}

export interface InternalDocLink {
  path: string
  headingId: string
}

// Parses a link to another Markdown document with its optional "#heading"
// fragment, or returns null for anything that is not such a link.
export function parseInternalDocLink(currentFile: string, href: string): InternalDocLink | null {
  const path = resolveDocPath(currentFile, href)
  if (!path || !MARKDOWN_EXT.test(path)) return null
  const hashIndex = href.indexOf('#')
  // Kept encoded, because markdown-it-anchor emits percent-encoded heading ids
  // and markdown-it encodes link hrefs the same way.
  const headingId = hashIndex === -1 ? '' : href.slice(hashIndex + 1)
  return { path, headingId }
}
