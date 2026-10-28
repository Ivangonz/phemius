import { act, fireEvent, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { usePlayer } from "@/hooks/usePlayer"
import { setAccessToken } from "@/lib/accessToken"
import { renderAppAt } from "@/test/renderApp"

const TRACK = {
  audioId: 7,
  title: "Deploying the Billing Service",
  meta: "teacher · af_heart",
}

function PlayerHarness() {
  const { play } = usePlayer()
  return (
    <>
      <button type="button" onClick={() => play(TRACK)}>
        Start test track
      </button>
      <label>
        Search
        <input />
      </label>
    </>
  )
}

function audioElement(): HTMLAudioElement {
  const audio = document.querySelector("audio")
  if (!audio) throw new Error("No audio element rendered")
  return audio
}

function blurActiveElement() {
  if (document.activeElement instanceof HTMLElement)
    document.activeElement.blur()
}

function playerBar() {
  return screen.getByRole("region", { name: "Player" })
}

async function startPlayback() {
  const user = userEvent.setup()
  const rendered = renderAppAt("/", <PlayerHarness />)
  await screen.findByRole("heading", { level: 1, name: "Library" })
  await user.click(screen.getByRole("button", { name: "Start test track" }))
  return { user, ...rendered }
}

describe("player bar", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("stays hidden until a track is loaded", async () => {
    renderAppAt("/", <PlayerHarness />)
    await screen.findByRole("heading", { level: 1, name: "Library" })

    expect(screen.queryByRole("region", { name: "Player" })).toBeNull()
  })

  it("plays the track and shows its title and meta", async () => {
    await startPlayback()

    expect(within(playerBar()).getByText(TRACK.title)).toBeInTheDocument()
    expect(within(playerBar()).getByText(TRACK.meta)).toBeInTheDocument()
    expect(
      within(playerBar()).getByRole("button", { name: "Pause" }),
    ).toBeInTheDocument()
    expect(audioElement().paused).toBe(false)
    expect(audioElement().getAttribute("src")).toBe("/api/audio/7/file")
  })

  it("passes the access token in the audio URL", async () => {
    setAccessToken("s3cret token")
    await startPlayback()

    expect(audioElement().getAttribute("src")).toBe(
      "/api/audio/7/file?token=s3cret%20token",
    )
  })

  it("keeps playing while navigating between screens", async () => {
    const { user } = await startPlayback()
    const audio = audioElement()
    const nav = screen.getByRole("navigation", { name: "Main" })

    await user.click(within(nav).getByRole("link", { name: "Sources" }))
    await screen.findByRole("heading", { level: 1, name: "Sources" })
    await user.click(within(nav).getByRole("link", { name: "Queue" }))
    await screen.findByRole("heading", { level: 1, name: "Queue" })

    expect(audioElement()).toBe(audio)
    expect(audio.paused).toBe(false)
    expect(within(playerBar()).getByText(TRACK.title)).toBeInTheDocument()
  })

  it("toggles playback with the k and Space shortcuts", async () => {
    const { user } = await startPlayback()
    const playPause = () =>
      within(playerBar()).getByRole("button", { name: /^(Play|Pause)$/ })

    expect(playPause()).toHaveAttribute("aria-keyshortcuts", "k Space")
    blurActiveElement()

    await user.keyboard("k")
    expect(audioElement().paused).toBe(true)
    expect(playPause()).toHaveAccessibleName("Play")

    await user.keyboard(" ")
    expect(audioElement().paused).toBe(false)
  })

  it("ignores shortcuts while typing in a form field", async () => {
    const { user } = await startPlayback()

    await user.type(screen.getByLabelText("Search"), "kjl ")

    expect(audioElement().paused).toBe(false)
    expect(audioElement().currentTime).toBe(0)
  })

  it("seeks with the keyboard", async () => {
    const { user } = await startPlayback()
    const seek = within(playerBar()).getByRole("slider", { name: "Seek" })
    blurActiveElement()

    await user.keyboard("l")
    expect(seek).toHaveAttribute("aria-valuetext", "0:30 of 6:18")

    await user.keyboard("j")
    expect(seek).toHaveAttribute("aria-valuetext", "0:15 of 6:18")

    within(playerBar())
      .getByRole("button", { name: "Forward 30 seconds" })
      .focus()
    await user.keyboard("{Enter}")
    expect(seek).toHaveAttribute("aria-valuetext", "0:45 of 6:18")

    // happy-dom does not move a range input on arrow keys; this is the change
    // the browser fires when it does.
    fireEvent.change(seek, { target: { value: "120" } })
    expect(audioElement().currentTime).toBe(120)
    expect(within(playerBar()).getByText("2:00")).toBeInTheDocument()
  })

  it("cycles the playback speed with the keyboard", async () => {
    const { user } = await startPlayback()
    const speed = within(playerBar()).getByRole("button", {
      name: "Playback speed 1.0 times",
    })

    speed.focus()
    await user.keyboard("{Enter}")

    expect(speed).toHaveAccessibleName("Playback speed 1.25 times")
    expect(speed).toHaveTextContent("1.25x")
    expect(audioElement().playbackRate).toBe(1.25)
  })

  it("publishes Media Session metadata and handles its actions", async () => {
    const handlers = new Map<string, (details: object) => void>()
    vi.stubGlobal(
      "MediaMetadata",
      class {
        init: object
        constructor(init: object) {
          this.init = init
        }
      },
    )
    const mediaSession = {
      metadata: null as { init: object } | null,
      playbackState: "none",
      setActionHandler: (action: string, handler: () => void) =>
        handlers.set(action, handler),
    }
    vi.stubGlobal("navigator", { ...navigator, mediaSession })

    await startPlayback()

    expect(mediaSession.metadata?.init).toMatchObject({
      title: TRACK.title,
      artist: TRACK.meta,
    })
    expect(mediaSession.playbackState).toBe("playing")
    act(() => handlers.get("seekto")?.({ seekTime: 90 }))
    expect(audioElement().currentTime).toBe(90)
  })
})
