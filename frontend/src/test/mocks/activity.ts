import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type ActivityEntry = components["schemas"]["ActivityEntry"]

export function activityHandler(entries: ActivityEntry[] = []) {
  return http.get("/api/sources/activity", ({ request }) => {
    const params = new URL(request.url).searchParams
    const sourceId = params.get("source_id")
    const limit = Number(params.get("limit") ?? 25)
    const offset = Number(params.get("offset") ?? 0)
    const found = entries.filter(
      (entry) => !sourceId || entry.source_id === Number(sourceId),
    )
    return HttpResponse.json({
      items: found.slice(offset, offset + limit),
      total: found.length,
      limit,
      offset,
    })
  })
}
