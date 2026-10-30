import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { sourcesQueryKey } from "./useSources"

export type SourceExclusion = components["schemas"]["SourceExclusion"]
type ExclusionPage = components["schemas"]["Page_SourceExclusion_"]

export const EXCLUSION_PAGE_SIZE = 25

export function useSourceExclusions(sourceId: number, offset: number) {
  return useQuery({
    queryKey: [...sourcesQueryKey, "exclusions", sourceId, offset],
    queryFn: () =>
      api.get<ExclusionPage>(
        withQuery(`/sources/${sourceId}/exclusions`, {
          order_by: "-created",
          limit: EXCLUSION_PAGE_SIZE,
          offset,
        }),
      ),
    placeholderData: keepPreviousData,
  })
}

// Lifting an exclusion records activity and may start a sync, so the source,
// its exclusions and the activity list all refresh.
export function useReimportFile(sourceId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (exclusion: SourceExclusion) =>
      api.delete(`/sources/${sourceId}/exclusions/${exclusion.id}`),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: sourcesQueryKey }),
  })
}
