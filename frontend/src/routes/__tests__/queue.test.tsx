import { act, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { makeJob } from "@/test/factories"
import { queueHandlers, type QueueState } from "@/test/mocks/queue"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const narrating = makeJob({
  id: 1,
  title: "Weekly Standup Notes",
  state: "running",
  stage: "narrating",
  progress: 0.5,
  tone: "executive",
  started: 1_761_600_100,
})
const waiting = makeJob({ id: 2, title: "Incident Response Runbook" })
const failed = makeJob({
  id: 3,
  title: "Remote Work Policy",
  state: "failed",
  error: "The model provider returned 402.",
  hint: "Add credits or lower the script length limit.",
})

function serveQueue(jobs = [narrating, waiting, failed]): QueueState {
  const state = { jobs: jobs.map((job) => ({ ...job })), isPaused: false }
  server.use(...queueHandlers(state))
  return state
}

function card(title: string) {
  return screen.getByRole("article", { name: title })
}

async function openQueue() {
  const user = userEvent.setup()
  renderAppAt("/queue")
  await screen.findByRole("article", { name: narrating.title })
  return user
}

describe("queue", () => {
  afterEach(() => vi.useRealTimers())

  it("shows each job's status, stage and progress in text", async () => {
    serveQueue()
    await openQueue()

    const running = card(narrating.title)
    expect(within(running).getByText("Narrating")).toBeInTheDocument()
    expect(
      within(running).getByText("Step 2 of 3: rendering the voice"),
    ).toBeInTheDocument()
    expect(within(running).getByText("executive · af_heart")).toBeVisible()
    expect(
      within(running).getByRole("progressbar", {
        name: `${narrating.title} progress`,
      }),
    ).toHaveAttribute("aria-valuenow", "50")
    expect(within(card(waiting.title)).getByText("Waiting")).toBeVisible()
    expect(
      screen.getByText(/1 running · 1 waiting · 1 failed\./),
    ).toBeInTheDocument()
  })

  it("explains a failed job and re-queues it on Retry", async () => {
    serveQueue()
    const user = await openQueue()

    const failedCard = card(failed.title)
    expect(within(failedCard).getByText("Failed")).toBeInTheDocument()
    expect(
      within(failedCard).getByText(/The model provider returned 402\./),
    ).toBeInTheDocument()
    expect(
      within(failedCard).getByText(/Add credits or lower the script length/),
    ).toBeInTheDocument()
    expect(
      within(failedCard).getByRole("link", { name: "Open settings" }),
    ).toHaveAttribute("href", "/settings")

    await user.click(
      within(failedCard).getByRole("button", { name: `Retry ${failed.title}` }),
    )

    expect(await within(card(failed.title)).findByText("Waiting")).toBeVisible()
    expect(within(card(failed.title)).queryByText(/returned 402/)).toBeNull()
  })

  it("removes a job from the queue when it is cancelled", async () => {
    serveQueue()
    const user = await openQueue()

    await user.click(
      within(card(waiting.title)).getByRole("button", {
        name: `Cancel ${waiting.title}`,
      }),
    )

    await vi.waitFor(() =>
      expect(screen.queryByRole("article", { name: waiting.title })).toBeNull(),
    )
  })

  it("pauses and resumes the queue", async () => {
    serveQueue()
    const user = await openQueue()

    await user.click(screen.getByRole("button", { name: "Pause queue" }))

    expect(
      await screen.findByRole("button", { name: "Resume queue" }),
    ).toBeInTheDocument()
    expect(screen.getByText(/The queue is paused\./)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Resume queue" }))

    expect(
      await screen.findByRole("button", { name: "Pause queue" }),
    ).toBeInTheDocument()
  })

  it("updates progress without moving keyboard focus", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const state = serveQueue()
    await openQueue()
    const cancel = within(card(narrating.title)).getByRole("button", {
      name: `Cancel ${narrating.title}`,
    })
    act(() => cancel.focus())

    state.jobs[0] = { ...state.jobs[0], stage: "converting", progress: 0 }
    await act(() => vi.advanceTimersByTimeAsync(2_500))

    expect(
      await within(card(narrating.title)).findByText("Converting"),
    ).toBeInTheDocument()
    expect(
      within(card(narrating.title)).getByRole("progressbar"),
    ).toHaveAttribute("aria-valuenow", "67")
    expect(document.activeElement).toBe(cancel)
  })

  it("says so when nothing is queued", async () => {
    serveQueue([])
    renderAppAt("/queue")

    expect(
      await screen.findByRole("heading", { name: "Nothing in the queue" }),
    ).toBeInTheDocument()
  })
})
