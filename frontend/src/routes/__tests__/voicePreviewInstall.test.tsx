import { act, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { VoiceView } from "@/hooks/useVoices"
import { server } from "@/test/mocks/server"
import { kokoroVoices, voicesPage } from "@/test/mocks/voices"
import { renderAppAt } from "@/test/renderApp"

function voiceList() {
  return screen.getByRole("group", { name: "Default voice (Kokoro)" })
}

function servePreviews() {
  const previewed: string[] = []
  server.use(
    http.post("/api/voices/:voiceId/preview", ({ params }) => {
      previewed.push(String(params.voiceId))
      return HttpResponse.json({
        url: `/api/voices/${String(params.voiceId)}/preview/file?sig=abc`,
        expires: 1_900_000_000,
      })
    }),
  )
  return previewed
}

const george = kokoroVoices[2]
const downloading = (done: number): VoiceView => ({
  ...george,
  download: { state: "downloading", done, total: 82_000_000 },
})
const installed: VoiceView = {
  ...george,
  is_installed: true,
  download: { state: "installed", done: 82_000_000, total: 82_000_000 },
}

// The download moves one step each time the list is polled.
function serveDownload(steps: VoiceView[]) {
  const calls = { lists: 0, downloads: 0 }
  let georgeNow: VoiceView = george
  server.use(
    http.get("/api/voices", () => {
      calls.lists += 1
      if (calls.downloads > 0) georgeNow = steps.shift() ?? georgeNow
      return HttpResponse.json(
        voicesPage([kokoroVoices[0], kokoroVoices[1], georgeNow]),
      )
    }),
    http.post("/api/voices/:voiceId/download", () => {
      calls.downloads += 1
      return HttpResponse.json(
        { state: "downloading", done: 0, total: 82_000_000 },
        { status: 202 },
      )
    }),
  )
  return calls
}

afterEach(() => {
  vi.useRealTimers()
})

describe("voice preview", () => {
  it("plays one preview at a time without touching the player bar", async () => {
    const previewed = servePreviews()
    const user = userEvent.setup()
    renderAppAt("/settings")

    await user.click(
      await screen.findByRole("button", { name: "Preview Heart" }),
    )
    expect(
      await screen.findByRole("button", { name: "Stop preview of Heart" }),
    ).toBeInTheDocument()
    expect(screen.getByText("Playing a preview of Heart.")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Preview Bella" }))

    expect(
      await screen.findByRole("button", { name: "Stop preview of Bella" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Preview Heart" }),
    ).toBeInTheDocument()
    expect(screen.getByText("Playing a preview of Bella.")).toBeInTheDocument()
    expect(previewed).toEqual(["kokoro:af_heart", "kokoro:af_bella"])
    expect(document.querySelector("audio")).not.toHaveAttribute("src")
    expect(screen.queryByRole("region", { name: "Player" })).toBeNull()
  })

  it("stops a preview when it is pressed again", async () => {
    servePreviews()
    const user = userEvent.setup()
    renderAppAt("/settings")

    await user.click(
      await screen.findByRole("button", { name: "Preview Heart" }),
    )
    await user.click(
      await screen.findByRole("button", { name: "Stop preview of Heart" }),
    )

    expect(
      screen.getByRole("button", { name: "Preview Heart" }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Playing a preview/)).toBeNull()
  })

  it("says why a preview could not play", async () => {
    server.use(
      http.post("/api/voices/:voiceId/preview", () =>
        HttpResponse.json(
          { detail: "Kokoro is not installed.", code: "voice_error" },
          { status: 503 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderAppAt("/settings")

    await user.click(
      await screen.findByRole("button", { name: "Preview Heart" }),
    )

    expect(
      await screen.findByText("Preview failed: Kokoro is not installed."),
    ).toBeInTheDocument()
  })
})

describe("voice install", () => {
  it("shows download progress, then Installed, and stops polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = serveDownload([downloading(41_000_000), installed])
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderAppAt("/settings")

    await user.click(
      await screen.findByRole("button", { name: "Install George" }),
    )

    expect(
      await screen.findByRole("progressbar", { name: "Downloading George" }),
    ).toHaveAttribute("value", "41000000")
    expect(
      screen.getByText("Downloading… 41.0 MB of 82.0 MB (50%)"),
    ).toBeInTheDocument()

    await act(() => vi.advanceTimersByTimeAsync(1_500))

    expect(
      within(voiceList()).getByRole("radio", { name: /George/ }),
    ).toHaveAccessibleName(/Installed/)
    expect(screen.queryByRole("progressbar")).toBeNull()
    expect(screen.queryByRole("button", { name: "Install George" })).toBeNull()
    const listsWhenDone = calls.lists
    await act(() => vi.advanceTimersByTimeAsync(5_000))
    expect(calls.lists).toBe(listsWhenDone)
    expect(calls.downloads).toBe(1)
  })

  it("does not poll the list while nothing downloads", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = serveDownload([])
    renderAppAt("/settings")
    await screen.findByRole("button", { name: "Install George" })
    const listsAtLoad = calls.lists

    await act(() => vi.advanceTimersByTimeAsync(5_000))

    expect(calls.lists).toBe(listsAtLoad)
  })
})
