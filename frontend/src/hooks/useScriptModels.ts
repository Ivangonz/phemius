import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"
import { modelsQueryKey } from "./useSettings"

export type OllamaModelList = components["schemas"]["OllamaModelList"]
export type ScriptModelConnection =
  components["schemas"]["ScriptModelConnection"]

export const ollamaModelsQueryKey = [...modelsQueryKey, "ollama"] as const

export function useOllamaModels(isEnabled: boolean) {
  return useQuery({
    queryKey: ollamaModelsQueryKey,
    queryFn: () => api.get<OllamaModelList>("/models/ollama"),
    enabled: isEnabled,
    retry: false,
  })
}

// Tests the saved settings, so unsaved changes must be saved first.
export function useCheckScriptModel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<ScriptModelConnection>("/models/check"),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: libraryConfigQueryKey }),
  })
}
