import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeSource } from "@/test/factories"
import { activityHandler } from "@/test/mocks/activity"
import { server } from "@/test/mocks/server"
import { serveSources } from "@/test/mocks/sources"
import { renderAppAt } from "@/test/renderApp"

type ActivityEntry = components["schemas"]["ActivityEntry"]

function entry(id: number, sourceId: number, item: string): ActivityEntry {
  return {
    id,
    source_id: sourceId,
    source_name: sourceId === 1 ? "notes" : "handbook",
    action: "imported",
    item,
    detail: "Audio queued in the suggested tone.",
    document_id: id,
    created: 1_761_600_000 - id,
  }
}

function openActivity(entries: ActivityEntry[]) {
  server.use(
    ...serveSources([
      makeSource({ id: 1, name: "notes" }),
      makeSource({ id: 2, name: "handbook" }),
    ]).handlers,
    activityHandler(entries),
  )
  renderAppAt("/sources")
  return screen.findByRole("region", { name: "Recent activity" })
}

describe("recent activity", () => {
  it("says what happened, with the action in words", async () => {
    const panel = await openActivity([entry(1, 1, "standup.md")])

    expect(
      await within(panel).findByText(
        "notes: Imported standup.md. Audio queued in the suggested tone.",
      ),
    ).toBeInTheDocument()
  })

  it("filters by source", async () => {
    const user = userEvent.setup()
    const panel = await openActivity([
      entry(1, 1, "standup.md"),
      entry(2, 2, "onboarding.md"),
    ])
    await within(panel).findByText(/onboarding\.md/)

    await user.selectOptions(within(panel).getByLabelText("Source"), "notes")

    expect(await within(panel).findByText(/standup\.md/)).toBeInTheDocument()
    expect(within(panel).queryByText(/onboarding\.md/)).toBeNull()
  })

  it("pages through older activity", async () => {
    const user = userEvent.setup()
    const entries = Array.from({ length: 12 }, (_, index) =>
      entry(index + 1, 1, `file-${index + 1}.md`),
    )
    const panel = await openActivity(entries)
    await within(panel).findByText(/file-1\.md/)

    await user.click(within(panel).getByRole("button", { name: "Next page" }))

    expect(await within(panel).findByText(/file-11\.md/)).toBeInTheDocument()
    expect(within(panel).queryByText(/file-1\.md/)).toBeNull()
  })

  it("says when there is no activity yet", async () => {
    const panel = await openActivity([])

    expect(
      await within(panel).findByText("Nothing has been imported yet."),
    ).toBeInTheDocument()
  })
})
