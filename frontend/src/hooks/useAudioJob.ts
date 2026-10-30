import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { queueQueryKey } from "./useQueue"

type QueuePage = components["schemas"]["QueuePage"]

const ACTIVE_JOBS_PATH = "/queue?state=queued&state=running&limit=100"
const ACTIVE_POLL_MS = 2_000

// Every version being made shares one request; `select` hands each version
// only its own job, so a version re-renders only when its progress changes.
export function useAudioJob(audioId: number, isActive: boolean) {
  const { data: job } = useQuery({
    queryKey: [...queueQueryKey, "active"],
    queryFn: () => api.get<QueuePage>(ACTIVE_JOBS_PATH),
    select: (page) => page.items.find((item) => item.audio_id === audioId),
    enabled: isActive,
    refetchInterval: isActive ? ACTIVE_POLL_MS : false,
  })
  return isActive ? job : undefined
}
