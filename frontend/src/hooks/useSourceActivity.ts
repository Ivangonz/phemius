import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { sourcesQueryKey } from "./useSources"

export type ActivityEntry = components["schemas"]["ActivityEntry"]
type ActivityPage = components["schemas"]["Page_ActivityEntry_"]

export const ACTIVITY_PAGE_SIZE = 10
const SYNC_POLL_MS = 2_000

type ActivityQuery = { sourceId: number | null; offset: number }

export function useSourceActivity(query: ActivityQuery, isPolling: boolean) {
  return useQuery({
    queryKey: [...sourcesQueryKey, "activity", query],
    queryFn: () =>
      api.get<ActivityPage>(
        withQuery("/sources/activity", {
          source_id: query.sourceId,
          limit: ACTIVITY_PAGE_SIZE,
          offset: query.offset,
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: isPolling ? SYNC_POLL_MS : false,
  })
}
