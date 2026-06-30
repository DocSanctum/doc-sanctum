import { watch, onUnmounted } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { Ref } from 'vue'

export function useSSE(sourceId: Ref<string | null>) {
  const qc = useQueryClient()
  let es: EventSource | null = null

  function connect(id: string) {
    es?.close()
    es = new EventSource(`/api/v1/sse/sources/${id}`)

    const fileEvents = ['file_created', 'file_deleted', 'file_modified', 'file_renamed']
    fileEvents.forEach(type => {
      es!.addEventListener(type, () => {
        qc.invalidateQueries({ queryKey: ['tree'] })
      })
    })

    es.addEventListener('tree_refreshed', () => {
      qc.invalidateQueries({ queryKey: ['tree'] })
      qc.invalidateQueries({ queryKey: ['sources'] })
    })
  }

  watch(sourceId, id => {
    if (id) connect(id)
    else es?.close()
  }, { immediate: true })

  onUnmounted(() => es?.close())
}
