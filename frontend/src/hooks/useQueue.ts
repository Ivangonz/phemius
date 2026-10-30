import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { isActiveJob } from "@/lib/jobStatus"
import { documentsQueryKey } from "./useDocuments"

export type Job = components["schemas"]["Job"]
type QueuePage = components["schemas"]["QueuePage"]
type QueueStatus = components["schemas"]["QueueStatus"]

export const queueQueryKey = ["queue"] as const

const ACTIVE_POLL_MS = 2_000
const QUEUE_PATH = "/queue?state=queued&state=running&state=failed&limit=100"

export function useQueue() {
  return useQuery({
    queryKey: [...queueQueryKey, "jobs"],
    queryFn: () => api.get<QueuePage>(QUEUE_PATH),
    refetchInterval: (query) =>
      query.state.data?.items.some(isActiveJob) ? ACTIVE_POLL_MS : false,
  })
}

function useQueueMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queueQueryKey }),
        queryClient.invalidateQueries({ queryKey: documentsQueryKey }),
      ]),
  })
}

export function useCancelJob() {
  return useQueueMutation((jobId: number) =>
    api.post<Job>(`/queue/${jobId}/cancel`),
  )
}

export function useRetryJob() {
  return useQueueMutation((jobId: number) =>
    api.post<Job>(`/queue/${jobId}/retry`),
  )
}

export function useSetQueuePaused() {
  return useQueueMutation((isPaused: boolean) =>
    api.post<QueueStatus>(isPaused ? "/queue/pause" : "/queue/resume"),
  )
}
