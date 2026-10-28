import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { setAccessToken } from "@/lib/accessToken"
import { api, ApiError, getErrorMessage } from "@/lib/api"
import { server } from "@/test/mocks/server"

describe("api client", () => {
  it("sends the saved access token as a bearer token", async () => {
    server.use(
      http.get("/api/health", ({ request }) =>
        HttpResponse.json({ auth: request.headers.get("Authorization") }),
      ),
    )
    setAccessToken("abc123")

    await expect(api.get("/health")).resolves.toEqual({
      auth: "Bearer abc123",
    })
  })

  it("omits the authorization header when no token is saved", async () => {
    server.use(
      http.get("/api/health", ({ request }) =>
        HttpResponse.json({ hasAuth: request.headers.has("Authorization") }),
      ),
    )

    await expect(api.get("/health")).resolves.toEqual({ hasAuth: false })
  })

  it("turns the standard error body into an ApiError", async () => {
    server.use(
      http.post("/api/docs", () =>
        HttpResponse.json(
          {
            detail: "Invalid request",
            code: "validation_error",
            hint: "Check the port.",
            errors: [{ field: "port", message: "Must be between 1 and 65535" }],
          },
          { status: 422 },
        ),
      ),
    )

    const error = await api.post("/docs", { port: 0 }).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 422,
      code: "validation_error",
      hint: "Check the port.",
    })
    expect(getErrorMessage(error)).toBe("Must be between 1 and 65535")
  })

  it("falls back to a generic error when the body is not the standard shape", async () => {
    server.use(
      http.get(
        "/api/docs",
        () => new HttpResponse("Bad gateway", { status: 502 }),
      ),
    )

    const error = await api.get("/docs").catch((e) => e)

    expect(error).toMatchObject({ status: 502, code: "http_error" })
    expect(getErrorMessage(error)).toBe("The server responded with 502.")
  })
})
