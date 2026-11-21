import { computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '../services/api'

const PLACEHOLDER_HOST = '<this-pc-ip>'

export function useShareLinks() {
  const queryClient = useQueryClient()

  const linksQuery = useQuery({ queryKey: ['share-links'], queryFn: api.listShares })
  const settingsQuery = useQuery({ queryKey: ['share-settings'], queryFn: api.getShareSettings })

  // An explicit base URL wins, then the Bonjour name start.sh detected. The
  // placeholder fallback is deliberately unusable so it is never sent as-is.
  const baseUrl = computed(() => {
    const s = settingsQuery.data.value
    if (!s) return ''
    return s.base_url || s.suggested_base_url || `http://${PLACEHOLDER_HOST}:${s.remote_port}`
  })
  const baseUrlIsPlaceholder = computed(() => baseUrl.value.includes(PLACEHOLDER_HOST))
  const remoteReachable = computed(() => settingsQuery.data.value?.remote_reachable ?? true)

  function linkFor(token: string): string {
    return `${baseUrl.value}/share/${token}`
  }

  const invalidateLinks = () => queryClient.invalidateQueries({ queryKey: ['share-links'] })

  const create = useMutation({
    mutationFn: (args: { sourceId: string; path: string; label?: string }) =>
      api.createShare(args.sourceId, args.path, args.label),
    onSuccess: invalidateLinks,
  })

  const revoke = useMutation({
    mutationFn: (id: string) => api.deleteShare(id),
    onSuccess: invalidateLinks,
  })

  const saveBaseUrl = useMutation({
    mutationFn: (value: string) => api.setShareBaseUrl(value),
    onSuccess: (data) => queryClient.setQueryData(['share-settings'], data),
  })

  return {
    linksQuery,
    settingsQuery,
    baseUrl,
    baseUrlIsPlaceholder,
    remoteReachable,
    linkFor,
    create,
    revoke,
    saveBaseUrl,
  }
}
