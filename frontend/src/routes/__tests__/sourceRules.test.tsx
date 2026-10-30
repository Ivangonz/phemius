import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type SourceView = components["schemas"]["SourceView"]

const AUTO_AUDIO = "Generate audio automatically for new documents"
const GLOBAL_RULES = makeSource({ id: 0, name: "global" }).effective_rules

function serve(source: Partial<SourceView>) {
  const handbook = makeSource({ id: 1, name: "handbook", ...source })
  server.use(...serveSources([handbook]).handlers)
}

async function openEdit(user: ReturnType<typeof userEvent.setup>) {
  renderAppAt("/sources")
  const card = await screen.findByRole("region", { name: "handbook" })
  await user.click(within(card).getByRole("button", { name: "Edit" }))
  return card
}

describe("a source's import rules", () => {
  it("keeps a toggled rule after a reload", async () => {
    const user = userEvent.setup()
    serve({})
    const card = await openEdit(user)
    const rule = within(card).getByRole("switch", { name: AUTO_AUDIO })
    expect(rule).toBeChecked()
    expect(rule).toHaveAccessibleDescription("Follows global setting: On")

    await user.click(rule)
    await waitFor(() =>
      expect(rule).toHaveAccessibleDescription("This source: Off"),
    )

    cleanup()
    const reloaded = await openEdit(user)
    expect(
      within(reloaded).getByRole("switch", { name: AUTO_AUDIO }),
    ).not.toBeChecked()
  })

  it("follows the global setting again after a reset", async () => {
    const user = userEvent.setup()
    serve({
      rules: { auto_audio: false },
      effective_rules: { ...GLOBAL_RULES, auto_audio: false },
    })
    const card = await openEdit(user)

    await user.click(
      within(card).getByRole("button", { name: `Reset ${AUTO_AUDIO}` }),
    )

    const rule = within(card).getByRole("switch", { name: AUTO_AUDIO })
    await waitFor(() =>
      expect(rule).toHaveAccessibleDescription("Follows global setting: On"),
    )
    expect(rule).toBeChecked()
    expect(rule).toHaveFocus()
  })

  it("saves the file types a source imports", async () => {
    const user = userEvent.setup()
    serve({})
    const card = await openEdit(user)
    const types = within(card).getByRole("group", { name: "File types" })

    await user.click(within(types).getByRole("checkbox", { name: ".pdf" }))

    expect(
      await within(types).findByText("This source: .md, .pdf, .txt"),
    ).toBeInTheDocument()
    expect(within(types).getByRole("checkbox", { name: ".pdf" })).toBeChecked()
  })
})
