import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type SetupCheck = components["schemas"]["SetupCheck"]
type SetupCheckRun = components["schemas"]["SetupCheckRun"]

export const healthyChecks: SetupCheck[] = [
  {
    id: "python",
    label: "Python version",
    detail: "Python 3.12 is in Kokoro's range (3.10 to 3.12).",
    status: "ok",
  },
  {
    id: "script_model",
    label: "Script model",
    detail: "anthropic/claude-haiku-5.5 (openrouter) answered in 142 ms.",
    status: "ok",
  },
  {
    id: "voice_engine",
    label: "Voice engine",
    detail: "Kokoro is ready.",
    status: "ok",
  },
]

export function makeCheckRun(
  checks: SetupCheck[],
  ranAt = "2026-10-28T09:00:00Z",
): SetupCheckRun {
  const count = (status: SetupCheck["status"]) =>
    checks.filter((check) => check.status === status).length
  return {
    checks,
    ran_at: ranAt,
    summary: {
      ok: count("ok"),
      optional: count("optional"),
      needs_attention: count("needs_attention"),
    },
  }
}

type ServeChecksOptions = {
  lastRun: SetupCheckRun | null
  runs: SetupCheckRun[]
}

// GET answers with the server's last run; each POST answers with the next of
// `runs` (repeating the last one) and becomes the new last run.
export function serveChecks({ lastRun, runs }: ServeChecksOptions) {
  const calls = { gets: 0, posts: 0 }
  let current = lastRun
  const handlers = [
    http.get("/api/checks", () => {
      calls.gets += 1
      return HttpResponse.json(current)
    }),
    http.post("/api/checks", () => {
      const run = runs[Math.min(calls.posts, runs.length - 1)]
      calls.posts += 1
      current = run ?? current
      return HttpResponse.json(run)
    }),
  ]
  return { handlers, calls }
}
