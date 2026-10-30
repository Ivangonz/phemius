import { act, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type SourceView = components["schemas"]["SourceView"]

function openSources(sources: SourceView[]) {
  server.use(...serveSources(sources).handlers)
  renderAppAt("/sources")
}

async function addFolder(path: string, user = userEvent.setup()) {
  await user.click(await screen.findByRole("button", { name: "Add source" }))
  await user.type(screen.getByLabelText("Folder path"), path)
  await user.click(screen.getByRole("button", { name: "Add folder" }))
}

describe("adding and editing a folder source", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("adds a folder, shows it syncing, then watching", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    openSources([])

    await addFolder(
      "/home/me/handbook",
      userEvent.setup({ advanceTimers: vi.advanceTimersByTime }),
    )

    const card = await screen.findByRole("region", { name: "handbook" })
    expect(within(card).getByText("Syncing")).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(2_500))
    expect(await within(card).findByText("Watching")).toBeInTheDocument()
    expect(screen.queryByLabelText("Folder path")).toBeNull()
  })

  it("shows the server's reason and hint when a folder cannot be added", async () => {
    openSources([])
    server.use(
      http.post("/api/sources", () =>
        HttpResponse.json(
          {
            detail: "This source already exists.",
            code: "duplicate_source",
            hint: "Edit the existing source instead.",
          },
          { status: 409 },
        ),
      ),
    )

    await addFolder("/home/me/notes")

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("This source already exists.")
    expect(alert).toHaveTextContent("Edit the existing source instead.")
    expect(screen.getByLabelText("Folder path")).toHaveValue("/home/me/notes")
  })

  it("asks for an absolute path before sending anything", async () => {
    openSources([])

    await addFolder("docs")

    expect(
      await screen.findByText(/Use an absolute path, such as/),
    ).toBeInTheDocument()
  })

  it("lists other source kinds as coming soon", async () => {
    openSources([])

    const tiles = await screen.findByRole("region", { name: "Add another" })

    expect(within(tiles).getByText("GitHub repository")).toBeInTheDocument()
    expect(within(tiles).getAllByText("Coming soon")).toHaveLength(3)
  })

  it("renames a locked source but keeps its path read-only", async () => {
    const user = userEvent.setup()
    openSources([makeSource({ id: 1, name: "inbox", is_locked: true })])
    const card = await screen.findByRole("region", { name: "inbox" })

    await user.click(within(card).getByRole("button", { name: "Edit" }))
    expect(within(card).getByLabelText("Folder path")).toHaveAttribute(
      "readonly",
    )
    const name = within(card).getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Team inbox")
    await user.click(within(card).getByRole("button", { name: "Save" }))

    expect(
      await screen.findByRole("region", { name: "Team inbox" }),
    ).toBeInTheDocument()
  })
})
