import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type DocumentListItem = components["schemas"]["DocumentListItem"]

function matches(document: DocumentListItem, params: URLSearchParams) {
  const category = params.get("category")
  const tone = params.get("tone")
  const status = params.get("status")
  const search = params.get("q")?.toLowerCase()
  return (
    (!category || document.category === category) &&
    (!tone || document.suggested_tone === tone) &&
    (!status || document.status === status) &&
    (!search || document.title.toLowerCase().includes(search))
  )
}

// Reads the library at request time, filtered and paged like the real
// endpoint, so a test can change it between polls.
export function documentsHandler(getDocuments: () => DocumentListItem[]) {
  return http.get("/api/docs", ({ request }) => {
    const params = new URL(request.url).searchParams
    const limit = Number(params.get("limit") ?? 25)
    const offset = Number(params.get("offset") ?? 0)
    const found = getDocuments().filter((document) => matches(document, params))
    return HttpResponse.json({
      items: found.slice(offset, offset + limit),
      total: found.length,
      limit,
      offset,
    })
  })
}
