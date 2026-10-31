import { useState } from "react"
import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
  type Mutation,
} from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"

export type SourceView = components["schemas"]["SourceView"]
type ImportRules = components["schemas"]["ImportRules"]
type RulesMutation = Mutation<SourceView, Error, ImportRules>
type SourcePage = components["schemas"]["Page_SourceView_"]
type NewSource = components["schemas"]["NewSourceRequest"]
type SourceChange = components["schemas"]["SourceChange"]
export type SourceAction = "pause" | "resume" | "sync"

// Activity lives under this key too, so one invalidation refreshes both.
export const sourcesQueryKey = ["sources"] as const
const SYNC_POLL_MS = 2_000
// A handful of sources is the norm; the API's largest page holds them all.
const SOURCE_PAGE_SIZE = 100

export function useSources(isSyncing: (source: SourceView) => boolean) {
  return useQuery({
    queryKey: [...sourcesQueryKey, "list"],
    queryFn: () =>
      api.get<SourcePage>(
        withQuery("/sources", { limit: SOURCE_PAGE_SIZE, offset: 0 }),
      ),
    refetchInterval: (query) =>
      query.state.data?.items.some(isSyncing) ? SYNC_POLL_MS : false,
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

export function useAddSource() {
  const invalidate = useInvalidateSources()
  return useMutation({
    mutationFn: (source: NewSource) => api.post<SourceView>("/sources", source),
    onSuccess: invalidate,
  })
}

export function useUpdateSource() {
  const invalidate = useInvalidateSources()
  return useMutation({
    mutationFn: ({ id, change }: { id: number; change: SourceChange }) =>
      api.patch<SourceView>(`/sources/${id}`, change),
    onSettled: invalidate,
  })
}

// Saves run one at a time in click order: a file types change sends the whole
// list, so a later save must not land before an earlier one.
export function useUpdateRules(sourceId: number) {
  const invalidate = useInvalidateSources()
  const [error, setError] = useState<unknown>(null)
  const mutationKey = [...sourcesQueryKey, "rules", sourceId]
  const { mutate } = useMutation({
    mutationKey,
    scope: { id: `source-rules-${sourceId}` },
    mutationFn: (rules: ImportRules) =>
      api.patch<SourceView>(`/sources/${sourceId}`, { rules }),
    onError: setError,
    onSettled: invalidate,
  })
  const queued = useMutationState<ImportRules | undefined, RulesMutation>({
    filters: { mutationKey, status: "pending" },
    select: (mutation) => mutation.state.variables,
  })
  const pending: ImportRules | undefined = queued.length
    ? Object.assign({}, ...queued)
    : undefined

  function save(rules: ImportRules) {
    setError(null)
    mutate(rules)
  }

  return { save, pending, error, isSaving: queued.length > 0 }
}

export function useDeleteSource() {
  const invalidate = useInvalidateSources()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/sources/${id}`),
    onSettled: invalidate,
  })
}
