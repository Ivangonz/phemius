import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"

type SourceView = components["schemas"]["SourceView"]
type NewSourceRequest = components["schemas"]["NewSourceRequest"]
type SourceChange = components["schemas"]["SourceChange"]
type ImportRules = components["schemas"]["ImportRules"]

// What a source applies for a rule it does not set.
const GLOBAL_RULES = makeSource({ id: 0, name: "global" }).effective_rules

function applyRules(source: SourceView, sent: ImportRules) {
  const merged = { ...source.rules, ...sent }
  const own = Object.fromEntries(
    Object.entries(merged).filter(([, value]) => value !== null),
  )
  return { rules: own, effective_rules: { ...GLOBAL_RULES, ...own } }
}

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
    http.post("/api/sources", async ({ request }) => {
      const body = (await request.json()) as NewSourceRequest
      const path = String(body.config.path)
      const id = Math.max(0, ...sources.map((source) => source.id)) + 1
      const name = body.name ?? path.split("/").pop() ?? path
      const added = makeSource({
        id,
        name,
        config: body.config,
        last_sync: null,
      })
      sources = [...sources, added]
      syncing = { id, listsLeft: 2 }
      return HttpResponse.json(added, { status: 201 })
    }),
    http.patch("/api/sources/:id", async ({ params, request }) => {
      const body = (await request.json()) as SourceChange
      const source = sources.find((item) => item.id === Number(params.id))
      return change(params.id, {
        ...(body.name ? { name: body.name } : {}),
        ...(body.config ? { config: body.config } : {}),
        ...(source && body.rules ? applyRules(source, body.rules) : {}),
      })
    }),
    http.delete("/api/sources/:id", ({ params }) => {
      sources = sources.filter((source) => source.id !== Number(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers }
}
