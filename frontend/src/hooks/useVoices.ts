import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"
import { voicesQueryKey } from "./useSettings"

export type VoiceView = components["schemas"]["VoiceView"]
type VoicePage = components["schemas"]["Page_VoiceView_"]
type DownloadProgress = components["schemas"]["DownloadProgress"]

// The API's largest page; engines offer a few dozen voices at most.
export const VOICE_PAGE_SIZE = 100
const DOWNLOAD_POLL_MS = 1_000

function isDownloading(page: VoicePage | undefined): boolean {
  return (
    page?.items.some((voice) => voice.download?.state === "downloading") ??
    false
  )
}

export function voicePath(voiceId: string): string {
  return `/voices/${encodeURIComponent(voiceId)}`
}

// Polling reads only the voice list, which sends no provider request.
export function useVoices() {
  return useQuery({
    queryKey: voicesQueryKey,
    queryFn: () =>
      api.get<VoicePage>(
        withQuery("/voices", {
          order_by: "default",
          limit: VOICE_PAGE_SIZE,
          offset: 0,
        }),
      ),
    refetchInterval: (query) =>
      isDownloading(query.state.data) ? DOWNLOAD_POLL_MS : false,
  })
}

export function useDownloadVoice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (voiceId: string) =>
      api.post<DownloadProgress>(`${voicePath(voiceId)}/download`),
    onSettled: () =>
      Promise.all(
        [voicesQueryKey, libraryConfigQueryKey].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}
