import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { activityHandler } from "@/test/mocks/activity"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type SourceView = components["schemas"]["SourceView"]
type SourceExclusion = components["schemas"]["SourceExclusion"]
type ActivityEntry = components["schemas"]["ActivityEntry"]

function excluded(id: number, name = `note-${id}.md`): SourceExclusion {
  return { id, name, item_key: `notes/${name}`, created: id }
}

function serve(source: Partial<SourceView>, exclusions: SourceExclusion[]) {
  const activity: ActivityEntry[] = []
  const handbook = makeSource({ id: 1, name: "handbook", ...source })
  server.use(
    ...serveSources([handbook], { 1: exclusions }, activity).handlers,
    activityHandler(activity),
  )
}

async function openExcluded(user: ReturnType<typeof userEvent.setup>) {
  renderAppAt("/sources")
  const card = await screen.findByRole("region", { name: "handbook" })
  await user.click(within(card).getByRole("button", { name: "Edit" }))
  const list = within(card).getByRole("region", { name: "Excluded files" })
  return { card, list }
}

describe("a source's excluded files", () => {
  it("re-imports a file and removes it from Excluded files", async () => {
    const user = userEvent.setup()
    serve({ status: "paused" }, [excluded(7, "old-notes.md")])
    const { list } = await openExcluded(user)

    await user.click(
      await within(list).findByRole("button", {
        name: "Re-import old-notes.md",
      }),
    )

    expect(await within(list).findByText("No excluded files.")).toBeVisible()
    expect(within(list).getByRole("status")).toHaveTextContent(
      "old-notes.md imports on the next sync.",
    )
  })

  it("shows an active source syncing and the re-import in activity", async () => {
    const user = userEvent.setup()
    serve({}, [excluded(7, "old-notes.md")])
    const { card, list } = await openExcluded(user)

    await user.click(
      await within(list).findByRole("button", {
        name: "Re-import old-notes.md",
      }),
    )

    expect(await within(card).findByText("Syncing")).toBeInTheDocument()
    const activity = screen.getByRole("region", { name: "Recent activity" })
    expect(
      await within(activity).findByText(
        /handbook: Brought back notes\/old-notes\.md\./,
      ),
    ).toBeInTheDocument()
  })

  it("steps back a page when the last file on a page is re-imported", async () => {
    const user = userEvent.setup()
    serve(
      { status: "paused" },
      Array.from({ length: 26 }, (_, index) => excluded(index + 1)),
    )
    const { list } = await openExcluded(user)
    await within(list).findByText("1–25 of 26")

    await user.click(within(list).getByRole("button", { name: "Next page" }))
    await user.click(
      await within(list).findByRole("button", { name: "Re-import note-1.md" }),
    )

    expect(
      await within(list).findByRole("button", { name: "Re-import note-26.md" }),
    ).toBeInTheDocument()
    expect(within(list).getAllByRole("listitem")).toHaveLength(25)
    expect(within(list).queryByRole("navigation", { name: "Pages" })).toBeNull()
  })

  it("keeps the file and says why when a re-import fails", async () => {
    const user = userEvent.setup()
    serve({ status: "paused" }, [excluded(7, "old-notes.md")])
    server.use(
      http.delete("/api/sources/:id/exclusions/:exclusionId", () =>
        HttpResponse.json(
          { detail: "Excluded item 7 not found", code: "not_found" },
          { status: 404 },
        ),
      ),
    )
    const { list } = await openExcluded(user)

    await user.click(
      await within(list).findByRole("button", {
        name: "Re-import old-notes.md",
      }),
    )

    expect(await within(list).findByRole("alert")).toHaveTextContent(
      "Excluded item 7 not found",
    )
    expect(
      within(list).getByRole("heading", { name: "Excluded files" }),
    ).toHaveFocus()
    expect(
      within(list).getByRole("button", { name: "Re-import old-notes.md" }),
    ).toBeEnabled()
  })
})
