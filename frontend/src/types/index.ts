export type SourceType = 'local' | 'github' | 'gitlab' | 'http' | 'localhost'
export type SourceStatus = 'active' | 'error' | 'syncing' | 'partial'
export type SourceIcon =
  | '📁' | '📦' | '🐙' | '🌐' | '💻' | '📚' | '🚀' | '🔧'
  | '📝' | '🗂️' | '⭐' | '🔥' | '🎯' | '📊' | '🧩' | '🔒'
  | '📖' | '🗃️' | '💾' | '☁️' | '🐳' | '💡' | '🏷️' | '📌'

export interface Source {
  id: string
  name: string
  type: SourceType
  path: string
  polling_interval_seconds: number | null
  created_at: string
  status: SourceStatus
  error_message: string | null
  icon: SourceIcon | null
  // Whether a per-source access token is stored — the token itself is
  // never returned by the API (specs/007-source-access-token).
  access_token_configured: boolean
  // Why the source is being re-indexed and how far along it is; the counts
  // are only set while a sync runs.
  index_reason: IndexReason | null
  index_done: number | null
  index_total: number | null
}

export interface IndexError {
  path: string
  kind: 'no_text' | 'fetch_failed' | 'index_failed'
  message: string
  updated_at: string
}

export type IndexReason = 'initial' | 'model' | 'chunking' | 'keyword' | 'recovery'

export interface FileEntry {
  path: string
  name: string
  is_dir: boolean
  size: number | null
  modified_at: string | null
  source_id: string
}

export interface DirectoryTree {
  source_id: string
  root: TreeNode
}

export interface TreeNode {
  path: string
  name: string
  is_dir: boolean
  size?: number | null
  modified_at?: string | null
  children?: TreeNode[]
}

export interface SSEEvent {
  event: 'file_created' | 'file_deleted' | 'file_modified' | 'file_renamed' | 'tree_refreshed'
  source_id: string
  path?: string
  old_path?: string
}

export interface McpTool {
  name: string
  description: string
}

export interface McpStatus {
  enabled: boolean
  sse_url: string
  http_url: string
  host_port: number
  tools: McpTool[]
  remote_port: number
  remote_reachable: boolean
  remote_token: string
}

export interface ShareLink {
  id: string
  token: string
  source_id: string
  source_name: string | null
  path: string
  label: string | null
  created_at: string
  last_accessed_at: string | null
  access_count: number
  // null when a remote source's tree is not cached yet.
  available: boolean | null
}

export interface ShareSettings {
  base_url: string
  suggested_base_url: string
  remote_port: number
  remote_reachable: boolean
}

export interface RegisterSourcePayload {
  name?: string
  type: SourceType
  path: string
  polling_interval_seconds?: number | null
  icon?: SourceIcon | null
  // Optional per-source PAT — only meaningful for github/gitlab (ignored
  // otherwise). Never echoed back by the API.
  access_token?: string
}

export interface PatchSourcePayload {
  name?: string
  polling_interval_seconds?: number | null
  icon?: SourceIcon | null
  // Omit entirely to keep the existing token. "" deletes it (falls back to
  // the server's global token). Non-empty replaces it.
  access_token?: string
}

export type DeploymentMode = 'standalone' | 'scaleout'

export interface DeploymentStatus {
  mode: DeploymentMode
}

export interface LocaleResult {
  locale: 'ko' | 'en' | 'unknown'
}

export type PaneId = 1 | 2
export type PaneColor = 'blue' | 'amber' | 'orange' | 'sky' | 'red' | 'purple' | 'gray'

export interface ViewerPaneState {
  id: PaneId
  sourceId: string | null
  filePath: string | null
}

export interface PaneMatch {
  paneId: PaneId
  color: PaneColor
}

export interface SearchMatch {
  source_id: string
  source_name: string
  path: string
  line_number: number
  line: string
  page?: number | null
  context: string[]
}

export interface SearchWarning {
  source_id?: string
  source_name?: string
  reason?: string
  message: string
}

export interface SearchResponse {
  query: string
  matches: SearchMatch[]
  warnings: SearchWarning[]
}

export type SearchMode = 'keyword' | 'semantic'

export interface SemanticMatch {
  source_id: string
  source_name: string
  path: string
  chunk_index: number
  page?: number | null
  score: number
  excerpt: string
}

export interface SemanticSearchResponse {
  query: string
  results: SemanticMatch[]
  warnings: SearchWarning[]
}
