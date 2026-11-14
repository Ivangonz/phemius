import { act, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, describe, expect, it, vi } from "vitest"
import { usePlayer } from "@/hooks/usePlayer"
import { server } from "@/test/mocks/server"
import { serveSettingsSaving } from "@/test/mocks/settings"
import { kokoroVoices, voicesHandler } from "@/test/mocks/voices"
import { renderAppAt } from "@/test/renderApp"

const previewUrl = (voiceId: string) =>
  `/api/voices/${voiceId}/preview/file?sig=abc`

// Heart's sample can be held back, to answer after a later click.
function servePreviews({ holdHeart = false } = {}) {
  const previewed: string[] = []
  const answered: string[] = []
  let releaseHeart = () => {}
  const heartGate = new Promise<void>((resolve) => {
    releaseHeart = resolve
  })
  server.use(
    http.post("/api/voices/:voiceId/preview", async ({ params }) => {
      const voiceId = String(params.voiceId)
      previewed.push(voiceId)
      if (holdHeart && voiceId === "kokoro:af_heart") await heartGate
      answered.push(voiceId)
      return HttpResponse.json({
        url: previewUrl(voiceId),
        expires: 1_900_000_000,
      })
    }),
  )
  return { previewed, answered, releaseHeart }
}

const TRACK = { audioId: 7, title: "Deploying the Billing Service", meta: "" }

function PlayerHarness() {
  const { play } = usePlayer()
  return (
    <button type="button" onClick={() => play(TRACK)}>
      Start test track
    </button>
  )
}

function playerAudio(): HTMLAudioElement {
  const audio = document.querySelector("audio")
  if (!audio) throw new Error("No player audio element rendered")
  return audio
}

// The preview element is not in the page, so record what each play() starts.
function recordPlayedSources() {
  const played: (string | null)[] = []
  const play = HTMLMediaElement.prototype.play
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (
    this: HTMLMediaElement,
  ) {
    played.push(this.getAttribute("src"))
    return play.call(this)
  })
  return played
}

afterEach(() => {
  vi.restoreAllMocks()
})

async function openSettings() {
  const user = userEvent.setup()
  renderAppAt("/settings", <PlayerHarness />)
  await screen.findByRole("button", { name: "Preview Heart" })
  return user
}

describe("voice preview", () => {
  it("plays one preview at a time and a second stops the first", async () => {
    const { previewed } = servePreviews()
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Preview Heart" }))
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
    expect(playerAudio()).not.toHaveAttribute("src")
    expect(screen.queryByRole("region", { name: "Player" })).toBeNull()
  })

  it("ignores a sample that answers after a later preview was asked for", async () => {
    const { answered, releaseHeart } = servePreviews({ holdHeart: true })
    const played = recordPlayedSources()
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Preview Heart" }))
    await user.click(screen.getByRole("button", { name: "Preview Bella" }))
    expect(
      await screen.findByText("Playing a preview of Bella."),
    ).toBeInTheDocument()

    releaseHeart()
    await waitFor(() => expect(answered).toContain("kokoro:af_heart"))
    // Asserting nothing changed: give the late answer time to arrive.
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)))

    expect(played).toEqual([previewUrl("kokoro:af_bella")])
    expect(screen.getByText("Playing a preview of Bella.")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Stop preview of Bella" }),
    ).toBeInTheDocument()
  })

  it("leaves a playing library track alone while a preview plays", async () => {
    servePreviews()
    const user = await openSettings()
    await user.click(screen.getByRole("button", { name: "Start test track" }))
    await waitFor(() => expect(playerAudio().paused).toBe(false))
    const trackSource = playerAudio().getAttribute("src")

    await user.click(screen.getByRole("button", { name: "Preview Heart" }))
    await screen.findByText("Playing a preview of Heart.")

    expect(playerAudio().paused).toBe(false)
    expect(playerAudio()).toHaveAttribute("src", trackSource)
    expect(
      within(screen.getByRole("region", { name: "Player" })).getByText(
        TRACK.title,
      ),
    ).toBeInTheDocument()
  })

  it("stops a preview when it is pressed again", async () => {
    servePreviews()
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Preview Heart" }))
    await user.click(
      await screen.findByRole("button", { name: "Stop preview of Heart" }),
    )

    expect(
      screen.getByRole("button", { name: "Preview Heart" }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Playing a preview/)).toBeNull()
  })

  it("stops a preview when its voice leaves the list", async () => {
    servePreviews()
    let isHeartListed = true
    server.use(
      ...serveSettingsSaving([]),
      voicesHandler(() =>
        kokoroVoices.filter(
          (voice) => isHeartListed || voice.label !== "Heart",
        ),
      ),
    )
    const user = await openSettings()
    await user.click(screen.getByRole("button", { name: "Preview Heart" }))
    await screen.findByText("Playing a preview of Heart.")

    isHeartListed = false
    await user.click(screen.getByRole("radio", { name: /Bella/ }))

    await waitFor(() =>
      expect(screen.queryByRole("radio", { name: /Heart/ })).toBeNull(),
    )
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
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Preview Heart" }))

    expect(
      await screen.findByText("Preview failed: Kokoro is not installed."),
    ).toBeInTheDocument()
  })
})
