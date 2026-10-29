import { act, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeDocument } from "@/test/factories"
import { documentsHandler } from "@/test/mocks/documents"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

type DocumentListItem = components["schemas"]["DocumentListItem"]

const deploying = makeDocument({
  id: 1,
  title: "Deploying the Billing Service",
  audio_id: 7,
  format: "m4a",
  size_bytes: 4_200_000,
  status: "done",
})
const onCall = makeDocument({
  id: 2,
  title: "On-call Handbook",
  category: "process / policy",
  suggested_tone: "executive",
})
const apiReference = makeDocument({
  id: 3,
  title: "Payments API Reference",
  category: "reference / API",
  suggested_tone: "neutral",
  audio_suitability: "not_recommended",
})

function serveLibrary(documents: DocumentListItem[]) {
  server.use(documentsHandler(() => documents))
}

function row(title: string) {
  return screen.getByRole("article", { name: title })
}

async function openLibrary(path = "/") {
  const user = userEvent.setup()
  const rendered = renderAppAt(path)
  await screen.findByRole("list", { name: "Documents" })
  return { user, ...rendered }
}

function audioElement(): HTMLAudioElement {
  const audio = document.querySelector("audio")
  if (!audio) throw new Error("No audio element rendered")
  return audio
}

describe("library", () => {
  afterEach(() => vi.useRealTimers())

  it("lists documents with their category, tone, status and length", async () => {
    serveLibrary([deploying, onCall])
    await openLibrary()

    const first = row(deploying.title)
    expect(within(first).getByText("how-to / tutorial")).toBeInTheDocument()
    expect(within(first).getByText("teacher")).toBeInTheDocument()
    expect(within(first).getByText("Ready")).toBeInTheDocument()
    expect(within(first).getByText("M4A · 4.2 MB")).toBeInTheDocument()
    expect(
      within(first).getByRole("link", { name: deploying.title }),
    ).toHaveAttribute("href", "/docs/1")
    expect(within(row(onCall.title)).getByText("No audio")).toBeInTheDocument()
    expect(screen.getByText("2 documents")).toBeInTheDocument()
  })

  it("flags documents that are not suited to audio in text", async () => {
    serveLibrary([apiReference])
    await openLibrary()

    expect(
      within(row(apiReference.title)).getByText("Not suited to audio"),
    ).toBeInTheDocument()
  })

  it("explains how to add the first document when the library is empty", async () => {
    renderAppAt("/")

    expect(
      await screen.findByRole("heading", { name: "Your library is empty" }),
    ).toBeInTheDocument()
    expect(screen.queryByRole("list", { name: "Documents" })).toBeNull()
  })

  it("narrows the list by category, tone and status", async () => {
    serveLibrary([deploying, onCall, apiReference])
    const { user, router } = await openLibrary()

    await user.selectOptions(
      screen.getByLabelText("Category"),
      "process / policy",
    )

    expect(await screen.findByText("1 document")).toBeInTheDocument()
    expect(row(onCall.title)).toBeInTheDocument()
    expect(screen.queryByRole("article", { name: deploying.title })).toBeNull()
    expect(router.state.location.search).toMatchObject({
      category: "process / policy",
    })

    await user.selectOptions(screen.getByLabelText("Category"), "")
    await user.selectOptions(screen.getByLabelText("Status"), "done")
    expect(await screen.findByText("1 document")).toBeInTheDocument()
    expect(row(deploying.title)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText("Status"), "")
    await user.selectOptions(screen.getByLabelText("Tone"), "executive")
    expect(await screen.findByText("1 document")).toBeInTheDocument()
    expect(row(onCall.title)).toBeInTheDocument()
  })

  it("searches by title and clears filters that match nothing", async () => {
    serveLibrary([deploying, onCall])
    const { user } = await openLibrary()

    await user.type(
      screen.getByRole("searchbox", { name: "Search titles" }),
      "handbook",
    )
    expect(await screen.findByText("1 document")).toBeInTheDocument()
    expect(row(onCall.title)).toBeInTheDocument()

    await user.type(
      screen.getByRole("searchbox", { name: "Search titles" }),
      "zzz",
    )
    expect(
      await screen.findByText("No documents match these filters."),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Clear filters" }))
    expect(await screen.findByText("2 documents")).toBeInTheDocument()
    expect(
      screen.getByRole("searchbox", { name: "Search titles" }),
    ).toHaveValue("")
  })

  it("restores filters from the address", async () => {
    serveLibrary([deploying, onCall])
    await openLibrary("/?status=no_audio")

    expect(screen.getByLabelText("Status")).toHaveValue("no_audio")
    expect(row(onCall.title)).toBeInTheDocument()
    expect(screen.queryByRole("article", { name: deploying.title })).toBeNull()
  })

  it("pages through a long library", async () => {
    const many = Array.from({ length: 30 }, (_, index) =>
      makeDocument({ id: index + 1, title: `Runbook ${index + 1}` }),
    )
    serveLibrary(many)
    const { user } = await openLibrary()

    expect(screen.getByText("1–25 of 30")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: "Next page" }))

    expect(await screen.findByText("26–30 of 30")).toBeInTheDocument()
    expect(row("Runbook 30")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled()
  })

  it("shows the error and its hint when the list cannot load", async () => {
    server.use(
      http.get("/api/docs", () =>
        HttpResponse.json(
          {
            detail: "The library database is locked",
            code: "database_error",
            hint: "Close other Phemius processes and try again.",
          },
          { status: 503 },
        ),
      ),
    )
    renderAppAt("/")

    const alert = await screen.findByRole("alert")
    expect(
      within(alert).getByText("The library database is locked"),
    ).toBeInTheDocument()
    expect(
      within(alert).getByText("Close other Phemius processes and try again."),
    ).toBeInTheDocument()
    expect(
      within(alert).getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument()
  })

  it("plays a ready document in the player bar", async () => {
    serveLibrary([deploying, onCall])
    const { user } = await openLibrary()

    expect(
      within(row(onCall.title)).queryByRole("button", { name: /^Play/ }),
    ).toBeNull()
    await user.click(
      within(row(deploying.title)).getByRole("button", {
        name: `Play ${deploying.title}`,
      }),
    )

    const player = screen.getByRole("region", { name: "Player" })
    expect(within(player).getByText(deploying.title)).toBeInTheDocument()
    expect(audioElement().getAttribute("src")).toBe("/api/audio/7/file")
    expect(
      within(row(deploying.title)).getByRole("button", {
        name: `Pause ${deploying.title}`,
      }),
    ).toBeInTheDocument()
  })

  it("keeps playing while polling updates other rows", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let library = [
      deploying,
      makeDocument({ ...onCall, status: "queued", audio_id: 8 }),
    ]
    server.use(documentsHandler(() => library))
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderAppAt("/")
    await screen.findByRole("list", { name: "Documents" })
    expect(within(row(onCall.title)).getByText("Queued")).toBeInTheDocument()

    await user.click(
      within(row(deploying.title)).getByRole("button", {
        name: `Play ${deploying.title}`,
      }),
    )
    const playingRow = row(deploying.title)
    const pauseButton = within(playingRow).getByRole("button", {
      name: `Pause ${deploying.title}`,
    })

    library = [
      deploying,
      makeDocument({
        ...onCall,
        status: "running",
        stage: "narrating",
        audio_id: 8,
      }),
    ]
    await act(() => vi.advanceTimersByTimeAsync(2_500))

    expect(
      await within(row(onCall.title)).findByText("Narrating"),
    ).toBeInTheDocument()
    expect(row(deploying.title)).toBe(playingRow)
    expect(within(playingRow).getByRole("button", { name: /^Pause/ })).toBe(
      pauseButton,
    )
    expect(audioElement().paused).toBe(false)
    expect(audioElement().getAttribute("src")).toBe("/api/audio/7/file")
  })
})
