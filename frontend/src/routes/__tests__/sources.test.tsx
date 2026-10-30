import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type SourceView = components["schemas"]["SourceView"]

function openSources(sources: SourceView[]) {
  const served = serveSources(sources)
  server.use(...served.handlers)
  renderAppAt("/sources")
  return served
}

const findCard = (name: string) => screen.findByRole("region", { name })

describe("sources screen", () => {
  it("shows a watched folder with its status in text and its path", async () => {
    openSources([makeSource({ id: 1, name: "notes" })])

    const card = await findCard("notes")

    expect(within(card).getByText("Watching")).toBeInTheDocument()
    expect(within(card).getByText("/home/me/notes")).toBeInTheDocument()
  })

  it("says so when there are no sources yet", async () => {
    openSources([])

    expect(await screen.findByText(/No sources yet/)).toBeInTheDocument()
  })

  it("pauses a source, and it stays paused on the next visit", async () => {
    const user = userEvent.setup()
    const served = openSources([makeSource({ id: 1, name: "notes" })])
    const card = await findCard("notes")

    await user.click(within(card).getByRole("button", { name: "Pause" }))

    expect(await within(card).findByText("Paused")).toBeInTheDocument()
    expect(within(card).getByRole("button", { name: "Resume" })).toBeVisible()
    cleanup()
    server.use(...served.handlers)
    renderAppAt("/sources")
    const reopened = await findCard("notes")
    expect(within(reopened).getByText("Paused")).toBeInTheDocument()
  })

  it("shows Error and the reason when the last sync failed", async () => {
    openSources([
      makeSource({ id: 1, name: "notes", error: "The folder is missing." }),
    ])

    const card = await findCard("notes")

    expect(within(card).getByText("Error")).toBeInTheDocument()
    expect(
      within(card).getByText("Last sync failed: The folder is missing."),
    ).toBeInTheDocument()
  })
})
