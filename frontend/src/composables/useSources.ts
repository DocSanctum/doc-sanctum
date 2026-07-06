import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { api } from '../services/api'
import type { RegisterSourcePayload, Source, SourceIcon } from '../types'

// 선택 가능한 소스 아이콘 팔레트 — 소스 추가/수정 화면의 아이콘 그리드에서 고를 수 있다.
export const SOURCE_ICON_OPTIONS: SourceIcon[] =
  ['📁', '📦', '🐙', '🌐', '💻', '📚', '🚀', '🔧', '📝', '🗂️', '⭐', '🔥', '🎯', '📊', '🧩', '🔒']

export function useSources() {
  const qc = useQueryClient()

  const sourcesQuery = useQuery({
    queryKey: ['sources'],
    queryFn: api.getSources,
    // Registration/refresh now index in the background (status: 'syncing'),
    // so poll briefly to pick up the active/error transition without
    // requiring the user to reload or reselect anything.
    refetchInterval: (query) => (query.state.data?.some((s) => s.status === 'syncing') ? 2000 : false),
  })

  const register = useMutation({
    mutationFn: (payload: RegisterSourcePayload) => api.registerSource(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSource(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const patch = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Pick<Source, 'name' | 'polling_interval_seconds' | 'icon'>> }) =>
      api.patchSource(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  return { sourcesQuery, register, remove, patch }
}
