import { computed, inject, provide, type ComputedRef, type InjectionKey, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '../services/api'
import type { IndexError } from '../types'
import { isIndexing } from '../utils/indexProgress'
import { useSources } from './useSources'

export const INDEX_ERRORS: InjectionKey<ComputedRef<Map<string, IndexError>>> = Symbol('indexErrors')

// Fetches the failed documents of the shown source and shares them with every
// TreeNode below. The key includes the sync state, so the list reloads when a
// sync ends.
export function provideIndexErrors(sourceId: Ref<string | null>) {
  const { sourcesQuery } = useSources()
  const syncState = computed(() => {
    const source = sourcesQuery.data.value?.find((s) => s.id === sourceId.value)
    return source ? `${source.status}:${isIndexing(source)}` : 'unknown'
  })
  const query = useQuery({
    queryKey: ['index-errors', sourceId, syncState],
    queryFn: () => api.getIndexErrors(sourceId.value!),
    enabled: () => !!sourceId.value,
  })
  const byPath = computed(() => new Map((query.data.value ?? []).map((e) => [e.path, e])))
  provide(INDEX_ERRORS, byPath)
  return byPath
}

export function useIndexErrors(): ComputedRef<Map<string, IndexError>> {
  return inject(INDEX_ERRORS, computed(() => new Map()))
}

// Counts failed documents inside a folder; the empty path is the root.
export function countErrorsUnder(errors: Map<string, IndexError>, dirPath: string): number {
  if (!dirPath) return errors.size
  const prefix = `${dirPath}/`
  let count = 0
  for (const path of errors.keys()) if (path.startsWith(prefix)) count += 1
  return count
}
