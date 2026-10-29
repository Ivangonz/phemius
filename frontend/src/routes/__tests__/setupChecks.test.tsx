import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { libraryConfigQueryKey } from "@/hooks/useLibraryConfig"
import type { components } from "@/lib/api-schema"
import { formatRunTime } from "@/lib/setupChecks"
import {
  healthyChecks,
  makeCheckRun,
  serveCheckRuns,
} from "@/test/mocks/checks"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

type SetupCheck = components["schemas"]["SetupCheck"]

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

async function openServerTab(...checks: SetupCheck[]) {
  const runs = serveCheckRuns(makeCheckRun(checks))
  server.use(runs.handler)
  const rendered = renderAppAt("/settings/server")
  await within(
    await screen.findByRole("region", { name: "Setup checks" }),
  ).findAllByRole("listitem")
  return { ...rendered, calls: runs.calls }
}

describe("setup checks card", () => {
  it("runs the checks on first load and labels each status in text", async () => {
    const { calls } = await openServerTab(
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
    expect(calls.count).toBe(1)
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
    const runs = serveCheckRuns(first, second)
    server.use(runs.handler)
    const user = userEvent.setup()
    renderAppAt("/settings/server")
    const card = await screen.findByRole("region", { name: "Setup checks" })
    expect(
      await within(card).findByText(
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
    expect(runs.calls.count).toBe(2)
  })

  it("links a script model problem to Models and voices", async () => {
    const user = userEvent.setup()
    const { router } = await openServerTab(unreachableModel)

    await user.click(
      within(checkRow("Script model")).getByRole("link", {
        name: "Fix in Models and voices",
      }),
    )

    expect(router.state.location.pathname).toBe("/settings")
  })

  it("explains when the checks cannot run", async () => {
    server.use(
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
    const { queryClient, calls } = await openServerTab(...healthyChecks)

    await queryClient.invalidateQueries({ queryKey: libraryConfigQueryKey })

    await waitFor(() => expect(calls.count).toBe(2))
  })
})

describe("sidebar status", () => {
  it("shows no warning when nothing needs attention", async () => {
    await openServerTab(...healthyChecks, missingFfmpeg)

    expect(
      within(sidebar()).queryByText(/needs? attention/),
    ).not.toBeInTheDocument()
  })

  it("warns in text and links server problems to the Server tab", async () => {
    await openServerTab(unreachableModel, unwritableLibrary)

    const warning = await within(sidebar()).findByRole("link", {
      name: /2 checks need attention/,
    })
    expect(warning).toHaveAttribute("href", "/settings/server")
  })

  it("links a script model problem to Models and voices", async () => {
    await openServerTab(unreachableModel)

    const warning = await within(sidebar()).findByRole("link", {
      name: /1 check needs attention/,
    })
    expect(warning).toHaveAttribute("href", "/settings")
  })
})
