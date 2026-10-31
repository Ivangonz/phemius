import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"

type SourceView = components["schemas"]["SourceView"]
type NewSourceRequest = components["schemas"]["NewSourceRequest"]
type SourceChange = components["schemas"]["SourceChange"]
type ImportRules = components["schemas"]["ImportRules"]
type SourceExclusion = components["schemas"]["SourceExclusion"]
type ActivityEntry = components["schemas"]["ActivityEntry"]

// What a source applies for a rule it does not set.
const GLOBAL_RULES = makeSource({ id: 0, name: "global" }).effective_rules

function applyRules(source: SourceView, sent: ImportRules) {
  const merged = { ...source.rules, ...sent }
  const own = Object.fromEntries(
    Object.entries(merged).filter(([, value]) => value !== null),
  )
  return { rules: own, effective_rules: { ...GLOBAL_RULES, ...own } }
}

function reimportEntry(
  source: SourceView,
  lifted: SourceExclusion,
  id: number,
): ActivityEntry {
  return {
    id,
    source_id: source.id,
    source_name: source.name,
    action: "reimport",
    item: lifted.item_key,
    document_id: null,
    detail: "Brought back from Excluded files; the next sync imports it.",
    created: 1_761_800_000,
  }
}

// One list behind every /api/sources route, so a change survives the refetch
// that follows it. A sync finishes on the second list request after it, so
// the first refetch still sees it running.
// A re-import adds its entry to `activity`; pass the same array to
// activityHandler to see it in Recent activity.
export function serveSources(
  initial: SourceView[],
  initialExclusions: Record<number, SourceExclusion[]> = {},
  activity: ActivityEntry[] = [],
) {
  let sources = [...initial]
  const exclusions = new Map(
    Object.entries(initialExclusions).map(([id, items]) => [Number(id), items]),
  )
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
      if (body.rules?.file_types?.length === 0)
        return HttpResponse.json(
          {
            detail: "Request validation failed",
            code: "validation_error",
            errors: [
              {
                field: "rules.file_types",
                message: "List should have at least 1 item",
              },
            ],
          },
          { status: 422 },
        )
      const source = sources.find((item) => item.id === Number(params.id))
      return change(params.id, {
        ...(body.name ? { name: body.name } : {}),
        ...(body.config ? { config: body.config } : {}),
        ...(source && body.rules ? applyRules(source, body.rules) : {}),
      })
    }),
    http.get("/api/sources/:id/exclusions", ({ params, request }) => {
      const search = new URL(request.url).searchParams
      const limit = Number(search.get("limit") ?? 25)
      const offset = Number(search.get("offset") ?? 0)
      const items = [...(exclusions.get(Number(params.id)) ?? [])].sort(
        (first, second) => second.created - first.created,
      )
      return HttpResponse.json({
        items: items.slice(offset, offset + limit),
        total: items.length,
        limit,
        offset,
      })
    }),
    http.delete("/api/sources/:id/exclusions/:exclusionId", ({ params }) => {
      const id = Number(params.id)
      const items = exclusions.get(id) ?? []
      const lifted = items.find(
        (item) => item.id === Number(params.exclusionId),
      )
      const source = sources.find((item) => item.id === id)
      if (!lifted || !source)
        return HttpResponse.json(
          { detail: "Excluded item not found", code: "not_found" },
          { status: 404 },
        )
      exclusions.set(
        id,
        items.filter((item) => item !== lifted),
      )
      activity.unshift(reimportEntry(source, lifted, activity.length + 1))
      if (source.status === "active") syncing = { id, listsLeft: 2 }
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete("/api/sources/:id", ({ params }) => {
      sources = sources.filter((source) => source.id !== Number(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers }
}
