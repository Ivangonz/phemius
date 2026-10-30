import { act, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { makeJob } from "@/test/factories"
import { queueHandlers, quietDay, todayStatsHandler } from "@/test/mocks/queue"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const nowSeconds = () => Date.now() / 1000

const finishedToday = makeJob({
  id: 5,
  title: "Deploying the Billing Service",
  state: "done",
  stage: "converting",
  progress: 1,
  audio_id: 70,
  finished: nowSeconds(),
  duration_seconds: 378,
  cost_usd: 0.0012,
})
const finishedLastWeek = makeJob({
  id: 6,
  title: "Why Audio Matters",
  state: "done",
  finished: nowSeconds() - 7 * 86_400,
})

function finishedList() {
  return screen.getByRole("list", { name: "Finished today" })
}

function audioElement(): HTMLAudioElement {
  const audio = document.querySelector("audio")
  if (!audio) throw new Error("No audio element rendered")
  return audio
}

describe("queue activity", () => {
  afterEach(() => vi.useRealTimers())

  it("lists today's finished audio and plays it", async () => {
    server.use(
      ...queueHandlers({
        jobs: [finishedToday, finishedLastWeek],
        isPaused: false,
      }),
    )
    const user = userEvent.setup()
    renderAppAt("/queue")

    const row = await within(
      await screen.findByRole("list", { name: "Finished today" }),
    ).findByRole("article", { name: finishedToday.title })
    expect(within(row).getByText("teacher · af_heart")).toBeInTheDocument()
    expect(within(row).getByText("6:18 of audio")).toBeInTheDocument()
    expect(within(row).getByText("$0.001")).toBeInTheDocument()
    expect(
      within(finishedList()).queryByText(finishedLastWeek.title),
    ).toBeNull()

    await user.click(
      within(row).getByRole("button", { name: `Play ${finishedToday.title}` }),
    )

    await waitFor(() =>
      expect(audioElement().getAttribute("src")).toBe("/api/audio/70/file"),
    )
  })

  it("shows today's totals in the Today panel", async () => {
    server.use(
      todayStatsHandler(() => ({
        ...quietDay,
        scripts_written: 9,
        audio_files: 7,
        narration_minutes: 31.4,
        estimated_cost_usd: 0.041,
      })),
    )
    renderAppAt("/queue")

    const panel = await screen.findByRole("complementary", { name: "Today" })
    expect(await within(panel).findByText("9")).toBeInTheDocument()
    expect(within(panel).getByText("7")).toBeInTheDocument()
    expect(within(panel).getByText("31 min")).toBeInTheDocument()
    expect(within(panel).getByText("$0.04")).toBeInTheDocument()
  })

  it("moves a job to Finished today and refreshes the totals when it finishes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const running = makeJob({ ...finishedToday, state: "running" })
    const state = { jobs: [running], isPaused: false }
    let stats = quietDay
    server.use(
      ...queueHandlers(state),
      todayStatsHandler(() => stats),
    )
    renderAppAt("/queue")
    await screen.findByRole("article", { name: running.title })

    state.jobs = [finishedToday]
    stats = { ...quietDay, audio_files: 1 }
    await act(() => vi.advanceTimersByTimeAsync(2_500))

    expect(
      await within(finishedList()).findByText(finishedToday.title),
    ).toBeInTheDocument()
    const panel = screen.getByRole("complementary", { name: "Today" })
    expect(await within(panel).findByText("1")).toBeInTheDocument()
  })
})
