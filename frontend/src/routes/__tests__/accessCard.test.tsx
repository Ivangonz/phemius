import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it } from "vitest"
import type { AccessMode, AccessStatus } from "@/hooks/useAccess"
import type { SettingsOverview } from "@/hooks/useSettings"
import { getAccessToken } from "@/lib/accessToken"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const NEW_TOKEN = "phm_new-token-from-the-server"

type ServerState = {
  savedMode: AccessMode
  isModeLocked: boolean
  access: AccessStatus
}

function overview(state: ServerState): SettingsOverview {
  return {
    values: {
      access_mode: {
        value: state.savedMode,
        source: state.isModeLocked ? "env" : "saved",
        is_locked: state.isModeLocked,
      },
    },
    secrets: {},
  }
}

function mockServer(changes: Partial<AccessStatus> = {}, isModeLocked = false) {
  const state: ServerState = {
    savedMode: "local",
    isModeLocked,
    access: {
      active_mode: "local",
      is_token_required: false,
      has_token: false,
      is_token_from_env: false,
      port: 8000,
      ...changes,
    },
  }
  server.use(
    http.get("/api/access", () => HttpResponse.json(state.access)),
    http.get("/api/settings", () => HttpResponse.json(overview(state))),
    http.patch("/api/settings", async ({ request }) => {
      const body = (await request.json()) as { access_mode: AccessMode }
      state.savedMode = body.access_mode
      return HttpResponse.json(overview(state))
    }),
    http.post("/api/access/token", () => {
      state.access = { ...state.access, has_token: true }
      return HttpResponse.json({ token: NEW_TOKEN })
    }),
  )
  return state
}

async function openAccessCard() {
  renderAppAt("/settings/server")
  return screen.findByRole("region", { name: "Access" })
}

describe("access card", () => {
  beforeEach(() => {
    mockServer()
  })

  it("shows the running mode and the port read-only", async () => {
    const card = await openAccessCard()

    expect(
      await within(card).findByRole("radio", { name: /This computer only/ }),
    ).toBeChecked()
    expect(within(card).getByLabelText("Port")).toHaveValue("8000")
    expect(within(card).getByLabelText("Port")).toHaveAttribute("readonly")
    expect(
      within(card).getByText("Phemius has no user accounts."),
    ).toBeInTheDocument()
  })

  it("saves a new mode and says it applies after a restart", async () => {
    const user = userEvent.setup()
    const state = mockServer()
    const card = await openAccessCard()

    await user.click(
      await within(card).findByRole("radio", { name: /Anyone on my network/ }),
    )

    expect(await within(card).findByText(/Restart Phemius/)).toBeVisible()
    expect(state.savedMode).toBe("network")
    expect(
      within(card).getByRole("radio", { name: /Anyone on my network/ }),
    ).toBeChecked()
  })

  it("prompts for the token on the next load after switching to network", async () => {
    const user = userEvent.setup()
    mockServer()
    const card = await openAccessCard()
    await user.click(
      await within(card).findByRole("radio", { name: /Anyone on my network/ }),
    )
    await within(card).findByText(/Restart Phemius/)
    cleanup()

    server.use(
      http.get("/api/access", () =>
        HttpResponse.json(
          { detail: "Access token required", code: "unauthorized" },
          { status: 401 },
        ),
      ),
    )
    renderAppAt("/settings/server")

    expect(
      await screen.findByRole("dialog", { name: "Access token required" }),
    ).toBeInTheDocument()
  })

  it("regenerates after confirming, shows the token once and stores it", async () => {
    const user = userEvent.setup()
    mockServer({
      active_mode: "network",
      is_token_required: true,
      has_token: true,
    })
    const card = await openAccessCard()

    await user.click(
      await within(card).findByRole("button", { name: "Regenerate" }),
    )
    expect(getAccessToken()).toBeNull()
    await user.click(
      within(card).getByRole("button", { name: "Regenerate token" }),
    )

    expect(await within(card).findByLabelText("New access token")).toHaveValue(
      NEW_TOKEN,
    )
    expect(getAccessToken()).toBe(NEW_TOKEN)
    expect(within(card).getByText(/other devices/i)).toBeVisible()

    cleanup()
    const reopened = await openAccessCard()
    await within(reopened).findByRole("button", { name: "Regenerate" })
    expect(within(reopened).queryByDisplayValue(NEW_TOKEN)).toBeNull()
  })

  it("keeps the token when the confirmation is cancelled", async () => {
    const user = userEvent.setup()
    mockServer({ has_token: true })
    const card = await openAccessCard()

    await user.click(
      await within(card).findByRole("button", { name: "Regenerate" }),
    )
    await user.click(within(card).getByRole("button", { name: "Cancel" }))

    expect(
      within(card).queryByRole("button", { name: "Regenerate token" }),
    ).toBeNull()
    expect(getAccessToken()).toBeNull()
  })

  it("copies the new token", async () => {
    const user = userEvent.setup()
    mockServer({ has_token: true })
    const card = await openAccessCard()
    await user.click(
      await within(card).findByRole("button", { name: "Regenerate" }),
    )
    await user.click(
      within(card).getByRole("button", { name: "Regenerate token" }),
    )

    await user.click(await within(card).findByRole("button", { name: "Copy" }))

    await waitFor(async () =>
      expect(await navigator.clipboard.readText()).toBe(NEW_TOKEN),
    )
    expect(within(card).getByText("Copied")).toBeInTheDocument()
  })

  it("hides Regenerate when the token comes from the environment", async () => {
    mockServer({
      active_mode: "network",
      is_token_required: true,
      has_token: true,
      is_token_from_env: true,
    })
    const card = await openAccessCard()

    expect(
      await within(card).findByText(/set by PHEMIUS_ACCESS_TOKEN/),
    ).toBeVisible()
    expect(
      within(card).queryByRole("button", { name: "Regenerate" }),
    ).toBeNull()
  })

  it("explains a mode set by the environment and disables the choice", async () => {
    mockServer({}, true)
    const card = await openAccessCard()

    expect(
      await within(card).findByText(/set by PHEMIUS_ACCESS_MODE/),
    ).toBeVisible()
    for (const radio of within(card).getAllByRole("radio")) {
      expect(radio).toBeDisabled()
    }
  })
})
