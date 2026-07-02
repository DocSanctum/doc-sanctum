import { useQuery } from '@tanstack/vue-query'
import { api } from '../services/api'

export function useDeploymentMode() {
  return useQuery({
    queryKey: ['deployment-mode'],
    queryFn: api.getDeploymentMode,
    // Fixed for the lifetime of a deployment (specs/004-scaleout-deployment
    // Assumptions: no runtime standalone <-> scaleout transitions).
    staleTime: Infinity,
  })
}
