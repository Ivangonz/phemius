import { z } from "zod"
import { getAccessToken } from "./accessToken"
import type { components } from "./api-schema"

const API_BASE = "/api"

const errorBodySchema = z.object({
  detail: z.string(),
  code: z.string(),
  hint: z.string().optional(),
  errors: z
    .array(z.object({ field: z.string(), message: z.string() }))
    .optional(),
})

type ErrorBody = z.infer<typeof errorBodySchema>
export type FieldError = NonNullable<ErrorBody["errors"]>[number]

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly hint: string | undefined
  readonly errors: FieldError[]

  constructor(status: number, body: ErrorBody) {
    super(body.detail)
    this.name = "ApiError"
    this.status = status
    this.code = body.code
    this.hint = body.hint
    this.errors = body.errors ?? []
  }
}

let handleUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  handleUnauthorized = handler
}

async function toApiError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null)
  const parsed = errorBodySchema.safeParse(body)
  return new ApiError(
    response.status,
    parsed.success
      ? parsed.data
      : {
          detail: `The server responded with ${response.status}.`,
          code: "http_error",
        },
  )
}

function buildInit(method: string, body: unknown): RequestInit {
  const headers = new Headers({ Accept: "application/json" })
  const token = getAccessToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (body === undefined || body instanceof FormData) {
    return { method, headers, body }
  }
  headers.set("Content-Type", "application/json")
  return { method, headers, body: JSON.stringify(body) }
}

async function send(
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, buildInit(method, body))
  if (response.ok) return response
  if (response.status === 401) handleUnauthorized?.()
  throw await toApiError(response)
}

async function sendJson<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await send(method, path, body)
  return response.json()
}

export const api = {
  get: <T>(path: string) => sendJson<T>("GET", path),
  post: <T>(path: string, body?: unknown) => sendJson<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => sendJson<T>("PATCH", path, body),
  delete: async (path: string): Promise<void> => {
    await send("DELETE", path)
  },
}

type QueryValue = string | number | boolean | null | undefined

export function withQuery(
  path: string,
  params: Record<string, QueryValue>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "")
      search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

type AudioUrl = components["schemas"]["AudioUrl"]

// An <audio> element cannot send headers, so the server hands out a
// short-lived signed URL for the file. The token never goes in a URL.
export async function audioFileUrl(audioId: number): Promise<string> {
  const { url } = await api.get<AudioUrl>(`/audio/${audioId}/url`)
  return url
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError)
    return error.errors[0]?.message ?? error.message
  if (error instanceof TypeError) return "Could not reach the Phemius server."
  if (error instanceof Error && error.message) return error.message
  return "Something unexpected happened. Please try again."
}
