import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"

export type VoiceEngineStatus = components["schemas"]["VoiceEngineStatus"]

// Tests the saved settings, so unsaved changes must be saved first. Only the
// config itself is refreshed: the setup checks under its key would call the
// script model again.
export function useCheckVoiceEngine() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<VoiceEngineStatus>("/voices/check"),
    onSettled: () =>
      queryClient.invalidateQueries({
        queryKey: libraryConfigQueryKey,
        exact: true,
      }),
  })
}
