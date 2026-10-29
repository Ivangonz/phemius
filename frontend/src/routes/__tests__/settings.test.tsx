import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { renderAppAt } from "@/test/renderApp"

function settingsNav() {
  return screen.getByRole("navigation", { name: "Settings sections" })
}

describe("settings tabs", () => {
  it("opens on Models and voices", async () => {
    renderAppAt("/settings")

    await screen.findByRole("heading", { level: 1, name: "Settings" })
    expect(
      within(settingsNav()).getByRole("link", { name: "Models and voices" }),
    ).toHaveAttribute("aria-current", "page")
    expect(
      within(settingsNav()).getByRole("link", {
        name: "Server and self-hosting",
      }),
    ).not.toHaveAttribute("aria-current")
  })

  it("switches to Server and self-hosting and keeps Settings active", async () => {
    const user = userEvent.setup()
    const { router } = renderAppAt("/settings")
    await screen.findByRole("heading", { level: 1, name: "Settings" })

    await user.click(
      within(settingsNav()).getByRole("link", {
        name: "Server and self-hosting",
      }),
    )

    expect(router.state.location.pathname).toBe("/settings/server")
    expect(
      within(settingsNav()).getByRole("link", {
        name: "Server and self-hosting",
      }),
    ).toHaveAttribute("aria-current", "page")
    expect(
      within(screen.getByRole("navigation", { name: "Main" })).getByRole(
        "link",
        { name: "Settings" },
      ),
    ).toHaveAttribute("aria-current", "page")
  })
})
