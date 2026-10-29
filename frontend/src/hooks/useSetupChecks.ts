import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"

export type SetupCheck = components["schemas"]["SetupCheck"]
export type SetupCheckRun = components["schemas"]["SetupCheckRun"]

export const setupChecksQueryKey = [...libraryConfigQueryKey, "checks"] as const

const runChecks = () => api.post<SetupCheckRun>("/checks")

// Running the checks calls the providers (a paid completion for a hosted
// script model), so a page load only reads the server's last run and runs
// them just when the server has none yet (after a restart). The key sits
// under the config key, so a settings save that invalidates the config
// refetches this query while it already holds a run: that refetch is the
// only way to get here with cached data, so it runs the checks again.
export function useSetupChecks() {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: setupChecksQueryKey,
    queryFn: async () => {
      if (queryClient.getQueryData(setupChecksQueryKey)) return runChecks()
      const lastRun = await api.get<SetupCheckRun | null>("/checks")
      return lastRun ?? runChecks()
    },
    staleTime: Infinity,
  })
}

export function useRunSetupChecks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: runChecks,
    onSuccess: (run) => queryClient.setQueryData(setupChecksQueryKey, run),
  })
}
