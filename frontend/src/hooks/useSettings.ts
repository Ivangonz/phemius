import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"

export type SettingsOverview = components["schemas"]["SettingsOverview"]
export type SettingsUpdate = components["schemas"]["Settings"]

export const settingsQueryKey = ["settings"] as const
// Anything read from the configured providers changes with the settings.
export const modelsQueryKey = ["models"] as const
export const voicesQueryKey = ["voices"] as const

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
    onSuccess: (overview) =>
      queryClient.setQueryData(settingsQueryKey, overview),
    onSettled: () =>
      Promise.all(
        [
          settingsQueryKey,
          libraryConfigQueryKey,
          modelsQueryKey,
          voicesQueryKey,
        ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      ),
  })
}
