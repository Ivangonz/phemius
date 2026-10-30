import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import {
  makeAudio,
  makeDocumentDetail,
  makeJob,
  makeVersion,
} from "@/test/factories"
import {
  documentHandlers,
  type DocumentFixture,
} from "@/test/mocks/documentDetail"
import { libraryConfig } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const TITLE = "Deploying the Billing Service"

function serveDocument(overrides: Partial<DocumentFixture> = {}) {
  const fixture: DocumentFixture = {
    document: makeDocumentDetail({ id: 1, title: TITLE }),
    versions: [makeVersion({ id: 1, number: 1 })],
    audio: [makeAudio({ id: 7, tone: "teacher" })],
    ...overrides,
  }
  server.use(
    ...documentHandlers(() => fixture),
    http.get("/api/config", () =>
      HttpResponse.json({
        ...libraryConfig,
        tones: {
          neutral: "Clear and calm, like a briefing.",
          podcast: "Energetic host walking through the topic.",
          teacher: "Patient and structured, with a recap.",
        },
        voices: {
          "kokoro:af_heart": "Heart, female (default)",
          "kokoro:bm_george": "George, male",
        },
        default_voice: "kokoro:af_heart",
      }),
    ),
  )
}

function generatePanel() {
  return screen.getByRole("complementary", { name: "Generate a new version" })
}

async function openDocument() {
  const user = userEvent.setup()
  renderAppAt("/docs/1")
  await screen.findByRole("heading", { level: 1, name: TITLE })
  await within(generatePanel()).findByRole("radio", { name: /Teacher/ })
  return user
}

describe("generating a version", () => {
  it("suggests the document's tone with its rationale and the default voice", async () => {
    serveDocument()
    await openDocument()
    const panel = generatePanel()

    expect(
      within(panel).getByText("It reads as a step-by-step how-to."),
    ).toBeInTheDocument()
    expect(
      within(panel).getByRole("radio", { name: /Teacher \(suggested\)/ }),
    ).toBeChecked()
    expect(within(panel).getByRole("combobox", { name: "Voice" })).toHaveValue(
      "kokoro:af_heart",
    )
  })

  it("adds a version in the list when generating audio and selects it", async () => {
    serveDocument()
    const user = await openDocument()
    const panel = generatePanel()

    await user.click(within(panel).getByRole("radio", { name: /Podcast/ }))
    await user.selectOptions(
      within(panel).getByRole("combobox", { name: "Voice" }),
      "kokoro:bm_george",
    )
    await user.click(
      within(panel).getByRole("button", { name: "Generate version" }),
    )

    const versions = screen.getByRole("list", { name: "Versions" })
    expect(
      await within(versions).findByRole("button", {
        name: "Podcast · bm_george · Queued",
        pressed: true,
      }),
    ).toBeInTheDocument()
    expect(
      await screen.findByText("The script is still being written."),
    ).toBeInTheDocument()
  })

  it("shows the queue's progress for a version being made", async () => {
    const running = makeAudio({
      id: 9,
      tone: "teacher",
      status: "running",
      stage: "narrating",
    })
    serveDocument({
      audio: [running],
      jobs: [
        makeJob({
          id: running.job_id,
          title: "Deploying the Billing Service",
          audio_id: 9,
          state: "running",
          stage: "narrating",
          progress: 0.4,
        }),
      ],
    })
    await openDocument()

    expect(
      await screen.findByRole("button", {
        name: "Teacher · af_heart · Narrating 40%",
      }),
    ).toBeInTheDocument()
  })

  it("explains why a version could not be queued", async () => {
    serveDocument()
    server.use(
      http.post("/api/docs/1/audio", () =>
        HttpResponse.json(
          {
            detail: "Kokoro is not installed.",
            code: "voice_error",
            hint: "Run `uv sync --extra kokoro`.",
          },
          { status: 502 },
        ),
      ),
    )
    const user = await openDocument()

    await user.click(
      within(generatePanel()).getByRole("button", { name: "Generate version" }),
    )

    const alert = await within(generatePanel()).findByRole("alert")
    expect(alert).toHaveTextContent("Kokoro is not installed.")
    expect(alert).toHaveTextContent("Run `uv sync --extra kokoro`.")
  })
})

describe("comparing versions", () => {
  it("shows two versions' scripts side by side", async () => {
    serveDocument({
      audio: [
        makeAudio({ id: 7, tone: "teacher" }),
        makeAudio({ id: 8, tone: "podcast" }),
      ],
    })
    const user = await openDocument()

    await user.click(
      screen.getByRole("button", { name: "Compare two versions" }),
    )

    const left = screen.getByRole("region", { name: "First version" })
    const right = screen.getByRole("region", { name: "Second version" })
    expect(await within(left).findByText("The podcast script.")).toBeVisible()
    expect(await within(right).findByText("The teacher script.")).toBeVisible()

    await user.selectOptions(
      within(right).getByRole("combobox", { name: "Second version" }),
      "8",
    )
    expect(await within(right).findByText("The podcast script.")).toBeVisible()
  })

  it("offers comparing only when there are two versions", async () => {
    serveDocument()
    await openDocument()

    expect(
      screen.queryByRole("button", { name: "Compare two versions" }),
    ).toBeNull()
  })
})
