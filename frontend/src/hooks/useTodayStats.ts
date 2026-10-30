import { useQuery } from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"

export type TodayStats = components["schemas"]["TodayStats"]

export const todayStatsQueryKey = ["stats", "today"] as const

export function useTodayStats() {
  const utcOffsetMinutes = -new Date().getTimezoneOffset()
  return useQuery({
    queryKey: [...todayStatsQueryKey, utcOffsetMinutes],
    queryFn: () =>
      api.get<TodayStats>(
        withQuery("/stats/today", { utc_offset_minutes: utcOffsetMinutes }),
      ),
  })
}
