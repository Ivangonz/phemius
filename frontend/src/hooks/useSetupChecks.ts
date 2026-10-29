import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"

export type SetupCheck = components["schemas"]["SetupCheck"]
export type SetupCheckRun = components["schemas"]["SetupCheckRun"]

// Nested under the config key so saving settings, which invalidates the
// config, also runs the checks again.
export const setupChecksQueryKey = [...libraryConfigQueryKey, "checks"] as const

// The query POSTs rather than reading GET /api/checks: the server's last run
// may predate a restart or a fix, so each app load runs the checks fresh.
// They call providers and take seconds, so they never go stale on their own;
// they rerun on load, on Run checks and when settings change.
export function useSetupChecks() {
  return useQuery({
    queryKey: setupChecksQueryKey,
    queryFn: () => api.post<SetupCheckRun>("/checks"),
    staleTime: Infinity,
  })
}
