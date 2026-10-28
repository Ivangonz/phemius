import { act, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it } from "vitest"
import { api, ApiError } from "@/lib/api"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const TOKEN = "s3cret-token"

describe("access token prompt", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/docs", ({ request }) => {
        if (request.headers.get("Authorization") === `Bearer ${TOKEN}`) {
          return HttpResponse.json({ items: [], total: 0 })
        }
        return HttpResponse.json(
          { detail: "Access token required", code: "unauthorized" },
          { status: 401 },
        )
      }),
    )
  })

  it("asks for the token after a 401 and sends it on later requests", async () => {
    const user = userEvent.setup()
    renderAppAt("/")
    await screen.findByRole("heading", { level: 1, name: "Library" })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    await act(() => expect(api.get("/docs")).rejects.toThrow(ApiError))

    const dialog = await screen.findByRole("dialog", {
      name: "Access token required",
    })
    await user.type(within(dialog).getByLabelText("Access token"), TOKEN)
    await user.click(within(dialog).getByRole("button", { name: "Save token" }))

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    )
    await expect(api.get("/docs")).resolves.toEqual({ items: [], total: 0 })
  })

  it("closes without saving when cancelled", async () => {
    const user = userEvent.setup()
    renderAppAt("/")
    await screen.findByRole("heading", { level: 1, name: "Library" })

    await act(() => expect(api.get("/docs")).rejects.toThrow(ApiError))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }))

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    )
    await expect(api.get("/docs")).rejects.toMatchObject({ status: 401 })
  })
})
