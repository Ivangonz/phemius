import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"

export type SourceView = components["schemas"]["SourceView"]
type SourcePage = components["schemas"]["Page_SourceView_"]
export type SourceAction = "pause" | "resume"

// Activity lives under this key too, so one invalidation refreshes both.
export const sourcesQueryKey = ["sources"] as const
// A handful of sources is the norm; the API's largest page holds them all.
const SOURCE_PAGE_SIZE = 100

export function useSources() {
  return useQuery({
    queryKey: [...sourcesQueryKey, "list"],
    queryFn: () =>
      api.get<SourcePage>(
        withQuery("/sources", { limit: SOURCE_PAGE_SIZE, offset: 0 }),
      ),
  })
}

function useInvalidateSources() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: sourcesQueryKey })
}

export function useSourceAction() {
  const invalidate = useInvalidateSources()
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: SourceAction }) =>
      api.post<SourceView>(`/sources/${id}/${action}`),
    onSettled: invalidate,
  })
}
