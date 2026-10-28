import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { renderAppAt } from "@/test/renderApp"

function mainNav() {
  return screen.getByRole("navigation", { name: "Main" })
}

describe("app shell", () => {
  it("renders the sidebar and the Library page at the root", async () => {
    renderAppAt("/")

    expect(
      await screen.findByRole("heading", { level: 1, name: "Library" }),
    ).toBeInTheDocument()
    expect(within(mainNav()).getByText("Phemius")).toBeInTheDocument()
    expect(
      within(mainNav()).getByRole("link", { name: "Library" }),
    ).toHaveAttribute("aria-current", "page")
  })

  it.each([
    ["Sources", "/sources"],
    ["Queue", "/queue"],
    ["Settings", "/settings"],
  ])("navigates to %s and marks it active", async (name, path) => {
    const user = userEvent.setup()
    const { router } = renderAppAt("/")
    await screen.findByRole("heading", { level: 1, name: "Library" })

    await user.click(within(mainNav()).getByRole("link", { name }))

    expect(
      await screen.findByRole("heading", { level: 1, name }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(path)
    expect(within(mainNav()).getByRole("link", { name })).toHaveAttribute(
      "aria-current",
      "page",
    )
    expect(
      within(mainNav()).getByRole("link", { name: "Library" }),
    ).not.toHaveAttribute("aria-current")
  })

  it("shows a not-found page for unknown paths", async () => {
    renderAppAt("/nowhere")

    expect(
      await screen.findByRole("heading", { name: "Page not found" }),
    ).toBeInTheDocument()
  })
})
