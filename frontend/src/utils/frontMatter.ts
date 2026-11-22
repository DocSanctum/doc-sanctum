import { load } from 'js-yaml'

export type FrontMatter = Record<string, unknown>

export interface FrontMatterResult {
  data: FrontMatter | null
  body: string
}

const FRONT_MATTER = /^---[ \t]*\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/

// Splits a leading YAML block off a document. The block is replaced with blank
// lines so rendered elements keep their original source line numbers.
export function extractFrontMatter(src: string): FrontMatterResult {
  const match = FRONT_MATTER.exec(src)
  if (!match) return { data: null, body: src }
  let data: unknown
  try {
    data = load(match[1])
  } catch {
    return { data: null, body: src }
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) return { data: null, body: src }
  const blankLines = '\n'.repeat(match[0].split('\n').length - 1)
  return { data: data as FrontMatter, body: blankLines + src.slice(match[0].length) }
}

export interface FrontMatterField {
  key: string
  value: string
}

export interface FrontMatterView {
  tags: string[]
  fields: FrontMatterField[]
}

function formatValue(value: unknown): string {
  if (value instanceof Date) return value.toISOString().slice(0, 10)
  if (Array.isArray(value)) return value.map(formatValue).join(', ')
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value ?? '')
}

// Shapes parsed metadata for display, pulling tags out as chips and
// flattening every other key to a single line of text.
export function toFrontMatterView(data: FrontMatter): FrontMatterView {
  const rawTags = data.tags ?? data.tag
  const tags = (Array.isArray(rawTags) ? rawTags : typeof rawTags === 'string' ? rawTags.split(/[,\s]+/) : [])
    .map((t) => String(t).replace(/^#/, '').trim())
    .filter(Boolean)
  const fields = Object.entries(data)
    .filter(([key, value]) => key !== 'tags' && key !== 'tag' && value !== null && value !== '')
    .map(([key, value]) => ({ key, value: formatValue(value) }))
  return { tags, fields }
}
