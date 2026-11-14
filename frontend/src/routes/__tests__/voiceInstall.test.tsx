import { act, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { VoiceView } from "@/hooks/useVoices"
import { libraryConfig } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { kokoroVoices, makeVoice, voicesPage } from "@/test/mocks/voices"
import { renderAppAt } from "@/test/renderApp"

const george = kokoroVoices[2]
const lewis = makeVoice({
  id: "kokoro:bm_lewis",
  label: "Lewis",
  accent: "British English, male",
  is_installed: false,
  size_bytes: 82_000_000,
})
const downloading = (done: number): VoiceView => ({
  ...george,
  download: { state: "downloading", done, total: 82_000_000 },
})
const installed: VoiceView = {
  ...george,
  is_installed: true,
  download: { state: "installed", done: 82_000_000, total: 82_000_000 },
}
const failed: VoiceView = {
  ...george,
  download: {
    state: "failed",
    done: 0,
    message: "The voice catalogue did not answer.",
    hint: "Check the connection and try again.",
  },
}

function voiceRadio(name: RegExp) {
  const list = screen.getByRole("group", { name: "Default voice (Kokoro)" })
  return within(list).getByRole("radio", { name })
}

// George moves one step each time the list is read after Install is pressed.
function serveVoices(first: VoiceView, steps: VoiceView[] = []) {
  const calls = { lists: 0, downloads: 0, configs: 0 }
  let georgeNow = first
  server.use(
    http.get("/api/voices", () => {
      calls.lists += 1
      if (calls.downloads > 0) georgeNow = steps.shift() ?? georgeNow
      return HttpResponse.json(
        voicesPage([kokoroVoices[0], kokoroVoices[1], georgeNow, lewis]),
      )
    }),
    http.post("/api/voices/:voiceId/download", () => {
      calls.downloads += 1
      return HttpResponse.json(
        { state: "downloading", done: 0, total: 82_000_000 },
        { status: 202 },
      )
    }),
    http.get("/api/config", () => {
      calls.configs += 1
      return HttpResponse.json(libraryConfig)
    }),
  )
  return calls
}

function refuseDownloads(status: number, detail: string, hint: string) {
  server.use(
    http.post("/api/voices/:voiceId/download", () =>
      HttpResponse.json({ detail, hint, code: "voice_error" }, { status }),
    ),
  )
}

function render() {
  const user = userEvent.setup(
    vi.isFakeTimers() ? { advanceTimers: vi.advanceTimersByTime } : {},
  )
  renderAppAt("/settings")
  return user
}

afterEach(() => {
  vi.useRealTimers()
})

describe("voice install", () => {
  it("shows progress, then Installed, keeping focus and announcing both ends", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = serveVoices(george, [downloading(41_000_000), installed])
    const user = render()

    await user.click(
      await screen.findByRole("button", { name: "Install George" }),
    )

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading George",
    })
    const progressText = "Downloading… 41.0 MB of 82.0 MB (50%)"
    expect(progress).toHaveAttribute("value", "41000000")
    expect(progress).toHaveAttribute("aria-valuetext", progressText)
    expect(progress).toHaveAccessibleDescription(progressText)
    expect(screen.getByText("Installing George…")).toBeInTheDocument()
    const installing = screen.getByRole("button", {
      name: "Installing… George",
    })
    expect(installing).toHaveFocus()
    expect(installing).toHaveAttribute("aria-disabled", "true")
    const waiting = screen.getByRole("button", {
      name: "Install Lewis: Waits for George",
    })
    expect(waiting).toHaveAttribute("aria-disabled", "true")
    await user.click(waiting)
    act(() => installing.focus())
    const configsBeforeFinish = calls.configs

    await act(() => vi.advanceTimersByTimeAsync(1_500))

    const georgeRadio = voiceRadio(/George/)
    expect(georgeRadio).toHaveAccessibleName(/male · Installed/)
    expect(georgeRadio).not.toHaveAccessibleName(/Not installed/)
    expect(georgeRadio).toHaveFocus()
    expect(screen.getByText("George is installed.")).toBeInTheDocument()
    expect(screen.queryByRole("progressbar")).toBeNull()
    expect(
      screen.getByRole("button", { name: "Install Lewis" }),
    ).toBeInTheDocument()
    expect(calls.configs).toBe(configsBeforeFinish + 1)
    const listsWhenDone = calls.lists
    await act(() => vi.advanceTimersByTimeAsync(5_000))
    expect(calls.lists).toBe(listsWhenDone)
    expect(calls.downloads).toBe(1)
  })

  it("does not poll the list while nothing downloads", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = serveVoices(george)
    render()
    await screen.findByRole("button", { name: "Install George" })
    const listsAtLoad = calls.lists

    await act(() => vi.advanceTimersByTimeAsync(5_000))

    expect(calls.lists).toBe(listsAtLoad)
  })

  it("shows a failed download with its message and hint", async () => {
    serveVoices(failed)
    render()

    expect(
      await screen.findByText(
        "Download failed: The voice catalogue did not answer.",
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Check the connection and try again."),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Install George" }),
    ).toBeInTheDocument()
  })

  it.each([
    [409, "Another voice is downloading.", "Wait for it to finish."],
    [503, "Downloads are stopping.", "Try again in a moment."],
  ])(
    "shows a refused start (%i) instead of the older failure",
    async (status, detail, hint) => {
      serveVoices(failed)
      refuseDownloads(status, detail, hint)
      const user = render()

      await user.click(
        await screen.findByRole("button", { name: "Install George" }),
      )

      expect(
        await screen.findByText(`Could not start: ${detail}`),
      ).toBeInTheDocument()
      expect(screen.getByText(hint)).toBeInTheDocument()
      expect(screen.queryByText(/Download failed/)).toBeNull()
    },
  )

  it("shows a download of unknown size without a percentage", async () => {
    serveVoices({
      ...george,
      download: { state: "downloading", done: 4_000_000, total: null },
    })
    render()

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading George",
    })
    expect(progress).not.toHaveAttribute("value")
    expect(progress).toHaveAttribute("aria-valuetext", "Downloading… 4.0 MB")
    expect(screen.getByText("Downloading… 4.0 MB")).toBeInTheDocument()
  })
})
