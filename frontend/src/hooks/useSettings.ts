import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"

export type SettingsOverview = components["schemas"]["SettingsOverview"]
export type SettingsUpdate = components["schemas"]["Settings"]

export const settingsQueryKey = ["settings"] as const

export function useSettings() {
  return useQuery({
    queryKey: settingsQueryKey,
    queryFn: () => api.get<SettingsOverview>("/settings"),
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (update: SettingsUpdate) =>
      api.patch<SettingsOverview>("/settings", update),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: settingsQueryKey }),
        queryClient.invalidateQueries({ queryKey: libraryConfigQueryKey }),
      ]),
  })
}
