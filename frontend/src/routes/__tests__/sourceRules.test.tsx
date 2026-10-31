import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { delay, http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type SourceView = components["schemas"]["SourceView"]

const AUTO_AUDIO = "Generate audio automatically for new documents"
const KEEP_VERSIONS = "Keep earlier versions when a document changes"
const GLOBAL_RULES = makeSource({ id: 0, name: "global" }).effective_rules

function serve(source: Partial<SourceView>) {
  const handbook = makeSource({ id: 1, name: "handbook", ...source })
  server.use(...serveSources([handbook]).handlers)
}

// Falls through to the served source after a pause, so saves overlap clicks.
function slowSaves() {
  server.use(
    http.patch("/api/sources/:id", async () => {
      await delay(50)
    }),
  )
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
    slowSaves()
    const card = await openEdit(user)

    await user.click(
      within(card).getByRole("button", { name: `Reset ${AUTO_AUDIO}` }),
    )

    const rule = within(card).getByRole("switch", { name: AUTO_AUDIO })
    expect(rule).toHaveAccessibleDescription("Follows global setting")
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

  it("keeps every change made while earlier saves are still running", async () => {
    const user = userEvent.setup()
    serve({})
    slowSaves()
    const card = await openEdit(user)
    const types = within(card).getByRole("group", { name: "File types" })

    await user.click(within(types).getByRole("checkbox", { name: ".pdf" }))
    await user.click(within(card).getByRole("switch", { name: AUTO_AUDIO }))
    await user.click(within(types).getByRole("checkbox", { name: ".docx" }))
    await user.click(within(card).getByRole("switch", { name: KEEP_VERSIONS }))

    const rules = within(card).getByRole("region", { name: "Import rules" })
    expect(within(rules).getByRole("status")).toHaveTextContent("Saving…")
    await waitFor(() =>
      expect(within(rules).getByRole("status")).toBeEmptyDOMElement(),
    )
    cleanup()
    const reloaded = await openEdit(user)
    expect(
      within(reloaded).getByRole("switch", { name: AUTO_AUDIO }),
    ).not.toBeChecked()
    expect(
      within(reloaded).getByRole("switch", { name: KEEP_VERSIONS }),
    ).not.toBeChecked()
    expect(
      within(reloaded).getByText("This source: .docx, .md, .pdf, .txt"),
    ).toBeInTheDocument()
  })

  it("keeps the last file type and resets file types to the default", async () => {
    const user = userEvent.setup()
    serve({
      rules: { file_types: [".md"] },
      effective_rules: { ...GLOBAL_RULES, file_types: [".md"] },
    })
    const card = await openEdit(user)
    const types = within(card).getByRole("group", { name: "File types" })

    expect(within(types).getByRole("checkbox", { name: ".md" })).toBeDisabled()
    expect(
      within(types).getByText("A source imports at least one type."),
    ).toBeInTheDocument()

    await user.click(
      within(types).getByRole("button", { name: "Reset File types" }),
    )

    expect(
      await within(types).findByText("Follows the default: .md, .txt"),
    ).toBeInTheDocument()
    expect(within(types).getByRole("checkbox", { name: ".md" })).toBeEnabled()
    expect(document.activeElement).toBeInstanceOf(HTMLInputElement)
  })

  it("shows why a rule was not saved and keeps the saved value", async () => {
    const user = userEvent.setup()
    serve({})
    server.use(
      http.patch("/api/sources/:id", () =>
        HttpResponse.json(
          {
            detail: "Request validation failed",
            code: "validation_error",
            errors: [
              { field: "rules.auto_audio", message: "Not a valid boolean" },
            ],
          },
          { status: 422 },
        ),
      ),
    )
    const card = await openEdit(user)
    const rule = within(card).getByRole("switch", { name: AUTO_AUDIO })

    await user.click(rule)

    expect(await within(card).findByRole("alert")).toHaveTextContent(
      "Not saved: Request validation failed",
    )
    await waitFor(() => expect(rule).toBeChecked())
    expect(rule).toHaveAccessibleDescription("Follows global setting: On")
  })
})
