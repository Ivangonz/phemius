import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import type { DocumentQuery } from "@/lib/librarySearch"

export type DocumentListItem = components["schemas"]["DocumentListItem"]
type DocumentPage = components["schemas"]["Page_DocumentListItem_"]

export const documentsQueryKey = ["docs"] as const

const ACTIVE_POLL_MS = 2_000
// Watched folders add documents in the background, so keep checking slowly.
const IDLE_POLL_MS = 30_000

function hasActiveJobs(page: DocumentPage | undefined): boolean {
  return Boolean(
    page?.items.some(
      (item) => item.status === "queued" || item.status === "running",
    ),
  )
}

// Rows are memoized, so handing back the previous object for an unchanged
// signature keeps a playing row from re-rendering on every poll.
function keepUnchangedRows(
  previous: DocumentPage | undefined,
  next: DocumentPage,
): DocumentPage {
  if (!previous) return next
  const known = new Map(previous.items.map((item) => [item.id, item]))
  const items = next.items.map((item) => {
    const old = known.get(item.id)
    return old?.signature === item.signature ? old : item
  })
  return { ...next, items }
}

export function useDocuments(query: DocumentQuery) {
  const queryClient = useQueryClient()
  const queryKey = [...documentsQueryKey, "list", query] as const

  return useQuery({
    queryKey,
    queryFn: async () => {
      const page = await api.get<DocumentPage>(withQuery("/docs", query))
      return keepUnchangedRows(
        queryClient.getQueryData<DocumentPage>(queryKey),
        page,
      )
    },
    placeholderData: keepPreviousData,
    refetchInterval: (current) =>
      hasActiveJobs(current.state.data) ? ACTIVE_POLL_MS : IDLE_POLL_MS,
  })
}
