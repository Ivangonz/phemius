import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { isJobActive } from "@/lib/documentStatus"

export type AudioDetail = components["schemas"]["Audio"]

const ACTIVE_POLL_MS = 2_000

export function audioQueryKey(audioId: number) {
  return ["audio", audioId] as const
}

export function useAudio(audioId: number) {
  return useQuery({
    queryKey: audioQueryKey(audioId),
    queryFn: () => api.get<AudioDetail>(`/audio/${audioId}`),
    refetchInterval: (current) =>
      current.state.data && isJobActive(current.state.data)
        ? ACTIVE_POLL_MS
        : false,
  })
}
