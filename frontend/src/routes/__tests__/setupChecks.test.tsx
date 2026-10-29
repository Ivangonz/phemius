import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { libraryConfigQueryKey } from "@/hooks/useLibraryConfig"
import type { components } from "@/lib/api-schema"
import { formatRunTime } from "@/lib/setupChecks"
import { healthyChecks, makeCheckRun, serveChecks } from "@/test/mocks/checks"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

type SetupCheck = components["schemas"]["SetupCheck"]
type SetupCheckRun = components["schemas"]["SetupCheckRun"]

const missingFfmpeg: SetupCheck = {
  id: "ffmpeg",
  label: "ffmpeg",
  detail: "ffmpeg is not installed; audio stays WAV.",
  status: "optional",
}

const unreachableModel: SetupCheck = {
  id: "script_model",
  label: "Script model",
  detail: "anthropic/claude-haiku-5.5 (openrouter): provider returned 401",
  status: "needs_attention",
  hint: "Check the API key in Settings.",
}

const unwritableLibrary: SetupCheck = {
  id: "library",
  label: "Library folder",
  detail: "/data is not writable.",
  status: "needs_attention",
  hint: "Make /data writable or set PHEMIUS_DATA_DIR.",
}

function checksCard() {
  return screen.getByRole("region", { name: "Setup checks" })
}

function checkRow(label: string) {
  return within(checksCard()).getByRole("listitem", { name: label })
}

function sidebar() {
  return screen.getByRole("navigation", { name: "Main" })
}

async function openServerTab(
  lastRun: SetupCheckRun | null,
  runs: SetupCheckRun[] = [],
) {
  const served = serveChecks({ lastRun, runs })
  server.use(...served.handlers)
  const rendered = renderAppAt("/settings/server")
  await within(
    await screen.findByRole("region", { name: "Setup checks" }),
  ).findAllByRole("listitem")
  return { ...rendered, calls: served.calls }
}

function openWithLastRun(...checks: SetupCheck[]) {
  return openServerTab(makeCheckRun(checks))
}

describe("setup checks card", () => {
  it("shows the server's last run without running the checks", async () => {
    const { calls } = await openWithLastRun(
      healthyChecks[0],
      missingFfmpeg,
      unwritableLibrary,
    )

    expect(within(checkRow("Python version")).getByText("OK")).toBeVisible()
    expect(within(checkRow("ffmpeg")).getByText("Optional")).toBeVisible()
    expect(
      within(checkRow("Library folder")).getByText("Needs attention"),
    ).toBeVisible()
    expect(
      within(checkRow("Library folder")).getByText(
        unwritableLibrary.hint ?? "",
      ),
    ).toBeVisible()
    expect(calls).toEqual({ gets: 1, posts: 0 })
  })

  it("runs the checks once when the server has no last run", async () => {
    const { calls } = await openServerTab(null, [makeCheckRun([missingFfmpeg])])

    expect(within(checkRow("ffmpeg")).getByText("Optional")).toBeVisible()
    expect(calls).toEqual({ gets: 1, posts: 1 })
  })

  it("runs the checks again and shows the new results and time", async () => {
    const first = makeCheckRun([missingFfmpeg], "2026-10-28T09:00:00Z")
    const second = makeCheckRun(
      [
        {
          ...missingFfmpeg,
          status: "ok",
          detail: "ffmpeg 7.1 converts audio.",
        },
      ],
      "2026-10-28T11:45:00Z",
    )
    const user = userEvent.setup()
    const { calls } = await openServerTab(first, [second])
    expect(
      within(checksCard()).getByText(
        `Last run at ${formatRunTime(first.ran_at)}.`,
      ),
    ).toBeVisible()

    await user.click(
      within(checksCard()).getByRole("button", { name: "Run checks" }),
    )

    expect(
      await within(checksCard()).findByText(
        `Last run at ${formatRunTime(second.ran_at)}.`,
      ),
    ).toBeVisible()
    expect(within(checkRow("ffmpeg")).getByText("OK")).toBeVisible()
    expect(
      within(checkRow("ffmpeg")).getByText("ffmpeg 7.1 converts audio."),
    ).toBeVisible()
    expect(calls).toEqual({ gets: 1, posts: 1 })
  })

  it("links a script model problem to Models and voices", async () => {
    const user = userEvent.setup()
    const { router } = await openWithLastRun(unreachableModel)

    await user.click(
      within(checkRow("Script model")).getByRole("link", {
        name: "Fix in Models and voices",
      }),
    )

    expect(router.state.location.pathname).toBe("/settings")
  })

  it("explains when the checks cannot run", async () => {
    server.use(
      http.get("/api/checks", () => HttpResponse.json(null)),
      http.post("/api/checks", () =>
        HttpResponse.json(
          { detail: "The server is busy.", code: "busy", hint: "Try later." },
          { status: 503 },
        ),
      ),
    )
    renderAppAt("/settings/server")

    const alert = await within(
      await screen.findByRole("region", { name: "Setup checks" }),
    ).findByRole("alert")
    expect(alert).toHaveTextContent("The server is busy.")
    expect(alert).toHaveTextContent("Try later.")
  })

  it("runs the checks again when settings change", async () => {
    const changed = makeCheckRun([unreachableModel], "2026-10-28T10:00:00Z")
    const { queryClient, calls } = await openServerTab(
      makeCheckRun(healthyChecks),
      [changed],
    )

    await queryClient.invalidateQueries({ queryKey: libraryConfigQueryKey })

    await waitFor(() =>
      expect(
        within(checkRow("Script model")).getByText("Needs attention"),
      ).toBeVisible(),
    )
    expect(calls).toEqual({ gets: 1, posts: 1 })
  })
})

describe("sidebar status", () => {
  it("shows no warning when nothing needs attention", async () => {
    await openWithLastRun(...healthyChecks, missingFfmpeg)

    expect(
      within(sidebar()).queryByText(/needs? attention/),
    ).not.toBeInTheDocument()
  })

  it("warns in text and links server problems to the Server tab", async () => {
    await openWithLastRun(unreachableModel, unwritableLibrary)

    const warning = await within(sidebar()).findByRole("link", {
      name: /2 checks need attention/,
    })
    expect(warning).toHaveAttribute("href", "/settings/server")
  })

  it("links a script model problem to Models and voices", async () => {
    await openWithLastRun(unreachableModel)

    const warning = await within(sidebar()).findByRole("link", {
      name: /1 check needs attention/,
    })
    expect(warning).toHaveAttribute("href", "/settings")
  })
})
