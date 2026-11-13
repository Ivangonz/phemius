import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey, type LibraryConfig } from "./useLibraryConfig"

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

const DEFAULT_KEYS: ReadonlySet<string> = new Set([
  "default_voice",
  "default_tone",
])

// A null default_voice falls back to the engine's first voice, which only the
// server knows, so that patch still refetches the config.
function isDefaultsOnly(update: SettingsUpdate): boolean {
  const keys = Object.keys(update)
  return (
    keys.length > 0 &&
    keys.every((key) => DEFAULT_KEYS.has(key)) &&
    update.default_voice !== null
  )
}

// GET /api/config checks the voice engine, a live request to a hosted engine,
// so a defaults-only save patches the cached config instead of refetching it.
function affectedQueries(update: SettingsUpdate) {
  if (isDefaultsOnly(update)) return [settingsQueryKey, voicesQueryKey]
  return [
    settingsQueryKey,
    libraryConfigQueryKey,
    modelsQueryKey,
    voicesQueryKey,
  ]
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    // Serializes saves from every settings section, not only this one, so the
    // last voice picked is the one that sticks.
    scope: { id: "settings" },
    mutationFn: (update: SettingsUpdate) =>
      api.patch<SettingsOverview>("/settings", update),
    onSuccess: (overview, update) => {
      queryClient.setQueryData(settingsQueryKey, overview)
      const voice = update.default_voice
      if (isDefaultsOnly(update) && voice)
        queryClient.setQueryData<LibraryConfig>(
          libraryConfigQueryKey,
          (config) => (config ? { ...config, default_voice: voice } : config),
        )
    },
    onSettled: (_overview, _error, update) =>
      Promise.all(
        affectedQueries(update).map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}
