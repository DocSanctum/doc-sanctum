import type { Source, DirectoryTree, RegisterSourcePayload, PatchSourcePayload, McpStatus, DeploymentStatus, LocaleResult, SearchResponse, SemanticSearchResponse } from '../types'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(body.detail ?? res.statusText), { status: res.status })
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  getSources: () => request<Source[]>('/sources'),

  registerSource: (payload: RegisterSourcePayload) =>
    request<Source>('/sources', { method: 'POST', body: JSON.stringify(payload) }),

  deleteSource: (id: string) =>
    request<void>(`/sources/${id}`, { method: 'DELETE' }),

  patchSource: (id: string, patch: PatchSourcePayload) =>
    request<Source>(`/sources/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  getTree: (sourceId: string) =>
    request<DirectoryTree>(`/sources/${sourceId}/tree`),

  getFileUrl: (sourceId: string, path: string) =>
    `${BASE}/sources/${sourceId}/file?path=${encodeURIComponent(path)}`,

  getFileContent: (sourceId: string, path: string) =>
    fetch(api.getFileUrl(sourceId, path)).then(r => {
      if (!r.ok) throw new Error(r.statusText)
      return r.text()
    }),

  refreshSource: (id: string) =>
    request<void>(`/sources/${id}/refresh`, { method: 'POST' }),

  getMcpStatus: () => request<McpStatus>('/mcp/status'),

  setMcpEnabled: (enabled: boolean) =>
    request<McpStatus>('/mcp/status', { method: 'PATCH', body: JSON.stringify({ enabled }) }),

  getDeploymentMode: () => request<DeploymentStatus>('/deployment'),

  getLocale: () => request<LocaleResult>('/locale'),

  search: (query: string, sourceId?: string) => {
    const params = new URLSearchParams({ q: query })
    if (sourceId) params.set('source_id', sourceId)
    return request<SearchResponse>(`/search?${params.toString()}`)
  },

  semanticSearch: (query: string, sourceId?: string, topK?: number) => {
    const params = new URLSearchParams({ q: query })
    if (sourceId) params.set('source_id', sourceId)
    if (topK) params.set('top_k', String(topK))
    return request<SemanticSearchResponse>(`/semantic-search?${params.toString()}`)
  },
}
