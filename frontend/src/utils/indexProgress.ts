import type { Source } from '../types'

export interface IndexProgress {
  // i18n key under sidebar.sourceList.indexing
  reasonKey: 'initial' | 'model' | 'chunking' | 'keyword' | 'recovery' | 'changes'
  done: number | null
  total: number | null
  percent: number | null
}

// A remote source's background poll re-indexes without switching to
// 'syncing', so live counts also mean the source is busy.
export function isIndexing(source: Source): boolean {
  return source.status === 'syncing' || source.index_total != null
}

export function indexProgress(source: Source): IndexProgress | null {
  if (!isIndexing(source)) return null
  const total = source.index_total ?? null
  const done = total == null ? null : Math.min(source.index_done ?? 0, total)
  const percent = total ? Math.round(((done ?? 0) / total) * 100) : null
  return { reasonKey: source.index_reason ?? 'changes', done, total, percent }
}
