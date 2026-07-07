import type { Source, DirectoryTree, RegisterSourcePayload, McpStatus, DeploymentStatus, LocaleResult } from '../types'

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

  patchSource: (id: string, patch: Partial<Pick<Source, 'name' | 'polling_interval_seconds' | 'icon'>>) =>
    request<Source>(`/sources/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  getTree: (sourceId: string) =>
    request<DirectoryTree>(`/sources/${sourceId}/tree`),

  getFileContent: (sourceId: string, path: string) =>
    fetch(`${BASE}/sources/${sourceId}/file?path=${encodeURIComponent(path)}`).then(r => {
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
}
