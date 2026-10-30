import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type SourceView = components["schemas"]["SourceView"]

// One list behind every /api/sources route, so a change survives the refetch
// that follows it. A sync finishes on the second list request after it, so
// the first refetch still sees it running.
export function serveSources(initial: SourceView[]) {
  let sources = [...initial]
  let syncing: { id: unknown; listsLeft: number } | null = null

  function change(id: unknown, patch: Partial<SourceView>) {
    sources = sources.map((source) =>
      source.id === Number(id) ? { ...source, ...patch } : source,
    )
    return HttpResponse.json(sources.find((source) => source.id === Number(id)))
  }

  function advanceSync() {
    if (!syncing) return
    syncing.listsLeft -= 1
    if (syncing.listsLeft > 0) return
    change(syncing.id, { last_sync: 1_761_700_000 })
    syncing = null
  }

  const handlers = [
    http.get("/api/sources", () => {
      advanceSync()
      return HttpResponse.json({
        items: sources,
        total: sources.length,
        limit: 100,
        offset: 0,
      })
    }),
    http.post("/api/sources/:id/pause", ({ params }) =>
      change(params.id, { status: "paused" }),
    ),
    http.post("/api/sources/:id/resume", ({ params }) =>
      change(params.id, { status: "active" }),
    ),
    http.post("/api/sources/:id/sync", ({ params }) => {
      syncing = { id: params.id, listsLeft: 2 }
      return change(params.id, {})
    }),
    http.delete("/api/sources/:id", ({ params }) => {
      sources = sources.filter((source) => source.id !== Number(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers }
}
