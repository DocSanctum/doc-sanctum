import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { api } from '../services/api'
import type { RegisterSourcePayload, Source } from '../types'

export function useSources() {
  const qc = useQueryClient()

  const sourcesQuery = useQuery({
    queryKey: ['sources'],
    queryFn: api.getSources,
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
    mutationFn: ({ id, data }: { id: string; data: Partial<Pick<Source, 'name' | 'polling_interval_seconds'>> }) =>
      api.patchSource(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  return { sourcesQuery, register, remove, patch }
}
