import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type SourceView = components["schemas"]["SourceView"]

// One list behind every /api/sources route, so a change survives the refetch
// that follows it.
export function serveSources(initial: SourceView[]) {
  let sources = [...initial]

  function change(id: unknown, patch: Partial<SourceView>) {
    sources = sources.map((source) =>
      source.id === Number(id) ? { ...source, ...patch } : source,
    )
    return HttpResponse.json(sources.find((source) => source.id === Number(id)))
  }

  const handlers = [
    http.get("/api/sources", () =>
      HttpResponse.json({
        items: sources,
        total: sources.length,
        limit: 100,
        offset: 0,
      }),
    ),
    http.post("/api/sources/:id/pause", ({ params }) =>
      change(params.id, { status: "paused" }),
    ),
    http.post("/api/sources/:id/resume", ({ params }) =>
      change(params.id, { status: "active" }),
    ),
  ]
  return { handlers }
}
