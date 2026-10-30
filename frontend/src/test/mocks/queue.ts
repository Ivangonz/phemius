import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type Job = components["schemas"]["Job"]

export type QueueState = { jobs: Job[]; isPaused: boolean }

function updateJob(state: QueueState, id: number, patch: Partial<Job>) {
  const job = state.jobs.find((candidate) => candidate.id === id)
  if (!job)
    return HttpResponse.json(
      { detail: "Job not found.", code: "not_found" },
      { status: 404 },
    )
  Object.assign(job, patch)
  return HttpResponse.json(job)
}

// Serves a mutable queue so a test can change jobs between polls and see
// what Cancel, Retry and Pause did to it.
export function queueHandlers(state: QueueState) {
  return [
    http.get("/api/queue", ({ request }) => {
      const states = new URL(request.url).searchParams.getAll("state")
      const items = state.jobs.filter(
        (job) => states.length === 0 || states.includes(job.state),
      )
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 100,
        offset: 0,
        is_paused: state.isPaused,
      })
    }),
    http.post("/api/queue/:jobId/cancel", ({ params }) =>
      updateJob(state, Number(params.jobId), { state: "cancelled" }),
    ),
    http.post("/api/queue/:jobId/retry", ({ params }) =>
      updateJob(state, Number(params.jobId), {
        state: "queued",
        error: null,
        hint: null,
      }),
    ),
    http.post("/api/queue/pause", () => {
      state.isPaused = true
      return HttpResponse.json({ is_paused: true })
    }),
    http.post("/api/queue/resume", () => {
      state.isPaused = false
      return HttpResponse.json({ is_paused: false })
    }),
  ]
}
