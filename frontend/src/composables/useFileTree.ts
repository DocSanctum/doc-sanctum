import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '../services/api'
import type { Ref } from 'vue'

export function useFileTree(sourceId: Ref<string | null>) {
  const qc = useQueryClient()

  const treeQuery = useQuery({
    queryKey: ['tree', sourceId],
    queryFn: () => api.getTree(sourceId.value!),
    enabled: () => !!sourceId.value,
  })

  function invalidate(id: string) {
    qc.invalidateQueries({ queryKey: ['tree', { value: id }] })
  }

  return { treeQuery, invalidate }
}
