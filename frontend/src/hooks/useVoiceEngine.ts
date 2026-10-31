import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey, type LibraryConfig } from "./useLibraryConfig"

export type VoiceEngineStatus = components["schemas"]["VoiceEngineStatus"]

// Tests the saved settings, so unsaved changes must be saved first. The result
// is written into the cached config rather than refetched: GET /api/config
// checks the engine again, a second request to a hosted engine.
export function useCheckVoiceEngine() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<VoiceEngineStatus>("/voices/check"),
    onSuccess: (status) =>
      queryClient.setQueryData<LibraryConfig>(
        libraryConfigQueryKey,
        (config) => (config ? { ...config, tts_status: status } : config),
      ),
  })
}
