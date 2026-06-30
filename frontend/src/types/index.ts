export type SourceType = 'local' | 'github' | 'http' | 'localhost'
export type SourceStatus = 'active' | 'error' | 'syncing'

export interface Source {
  id: string
  name: string
  type: SourceType
  path: string
  polling_interval_seconds: number | null
  created_at: string
  status: SourceStatus
  error_message: string | null
}

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

export interface RegisterSourcePayload {
  name?: string
  type: SourceType
  path: string
  polling_interval_seconds?: number | null
}
