import { z } from "zod"
import type { components, operations } from "./api-schema"

export type DocumentStatus = components["schemas"]["DocumentStatus"]
export type DocumentQuery = NonNullable<
  operations["list_documents_api_docs_get"]["parameters"]["query"]
>
type DocumentOrder = NonNullable<DocumentQuery["order_by"]>

export const PAGE_SIZE = 25

export const DOCUMENT_STATUSES = [
  "done",
  "running",
  "queued",
  "failed",
  "cancelled",
  "no_audio",
] as const satisfies readonly DocumentStatus[]

export const DOCUMENT_ORDERS = [
  "-created",
  "created",
  "title",
  "-updated",
] as const satisfies readonly DocumentOrder[]

// Mirrors the analyzer's categories, which /api/config does not expose yet.
export const CATEGORIES = [
  "how-to / tutorial",
  "reference / API",
  "architecture / design",
  "process / policy",
  "meeting notes / status",
  "proposal / spec",
  "narrative / essay",
  "other",
]

const text = z.coerce.string().optional().catch(undefined)

export const librarySearchSchema = z.object({
  q: text,
  category: text,
  tone: text,
  status: z.enum(DOCUMENT_STATUSES).optional().catch(undefined),
  order: z.enum(DOCUMENT_ORDERS).optional().catch(undefined),
  page: z.number().int().min(1).optional().catch(undefined),
})

export type LibrarySearch = z.infer<typeof librarySearchSchema>

export function parseStatus(value: string): LibrarySearch["status"] {
  return librarySearchSchema.shape.status.parse(value || undefined)
}

export function parseOrder(value: string): LibrarySearch["order"] {
  return librarySearchSchema.shape.order.parse(value || undefined)
}

export function hasFilters(search: LibrarySearch): boolean {
  return Boolean(search.q || search.category || search.tone || search.status)
}

export function toDocumentQuery(search: LibrarySearch): DocumentQuery {
  return {
    q: search.q || undefined,
    category: search.category || undefined,
    tone: search.tone || undefined,
    status: search.status,
    order_by: search.order ?? "-created",
    limit: PAGE_SIZE,
    offset: ((search.page ?? 1) - 1) * PAGE_SIZE,
  }
}
