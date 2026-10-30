import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { isActiveJob } from "@/lib/jobStatus"
import { documentsQueryKey } from "./useDocuments"
import { todayStatsQueryKey } from "./useTodayStats"

export type Job = components["schemas"]["Job"]
type QueuePage = components["schemas"]["QueuePage"]
type QueueStatus = components["schemas"]["QueueStatus"]

export const queueQueryKey = ["queue"] as const
const jobsQueryKey = [...queueQueryKey, "jobs"] as const
const finishedQueryKey = [...queueQueryKey, "finished"] as const

const ACTIVE_POLL_MS = 2_000
const QUEUE_PATH = "/queue?state=queued&state=running&state=failed&limit=100"
const FINISHED_PATH = "/queue?state=done&limit=100"

function hasJobLeft(previous: QueuePage | undefined, next: QueuePage) {
  const remaining = new Set(next.items.map((job) => job.id))
  return Boolean(previous?.items.some((job) => !remaining.has(job.id)))
}

export function useQueue() {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: jobsQueryKey,
    queryFn: async () => {
      const page = await api.get<QueuePage>(QUEUE_PATH)
      // Finished jobs and today's totals only change when a job leaves the
      // queue, so refresh them then rather than polling them as well.
      if (hasJobLeft(queryClient.getQueryData(jobsQueryKey), page)) {
        void queryClient.invalidateQueries({ queryKey: finishedQueryKey })
        void queryClient.invalidateQueries({ queryKey: todayStatsQueryKey })
      }
      return page
    },
    refetchInterval: (query) =>
      query.state.data?.items.some(isActiveJob) ? ACTIVE_POLL_MS : false,
  })
}

function startOfLocalDay(): number {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  return start.getTime() / 1000
}

// The list is newest-created first, so a job queued long ago that finished
// today can fall outside the page; the Today panel's totals stay exact.
export function useFinishedToday() {
  return useQuery({
    queryKey: finishedQueryKey,
    queryFn: () => api.get<QueuePage>(FINISHED_PATH),
    select: (page) => {
      const dayStart = startOfLocalDay()
      return page.items.filter((job) => (job.finished ?? 0) >= dayStart)
    },
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
