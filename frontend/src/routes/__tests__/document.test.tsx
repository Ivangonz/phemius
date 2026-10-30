import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { makeAudio, makeDocumentDetail, makeVersion } from "@/test/factories"
import {
  documentHandlers,
  type DocumentFixture,
} from "@/test/mocks/documentDetail"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

const TITLE = "Deploying the Billing Service"

const teacher = makeAudio({ id: 7, tone: "teacher" })
const podcast = makeAudio({
  id: 8,
  tone: "podcast",
  voice: "kokoro:bm_george",
  duration_seconds: 341,
  format: "wav",
  conversion_note: "ffmpeg is not installed, so this audio stayed WAV.",
})

function serveDocument(overrides: Partial<DocumentFixture> = {}) {
  const fixture: DocumentFixture = {
    document: makeDocumentDetail({ id: 1, title: TITLE }),
    versions: [makeVersion({ id: 1, number: 1 })],
    audio: [teacher, podcast],
    ...overrides,
  }
  server.use(...documentHandlers(() => fixture))
}

function versionButton(name: string) {
  const versions = screen.getByRole("list", { name: "Versions" })
  return within(versions).getByRole("button", { name })
}

async function openDocument(path = "/docs/1") {
  const user = userEvent.setup()
  renderAppAt(path)
  await screen.findByRole("heading", { level: 1, name: TITLE })
  return user
}

describe("document page", () => {
  it("shows the document's category, suitability, source and summary", async () => {
    serveDocument()
    await openDocument()

    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" })
    expect(
      within(breadcrumb).getByRole("link", { name: "Library" }),
    ).toHaveAttribute("href", "/")
    expect(screen.getByText("how-to / tutorial")).toBeInTheDocument()
    expect(screen.getByText("Great for audio")).toBeInTheDocument()
    expect(
      screen.getByText(/github: acme\/billing · docs\/deploy-guide\.md/),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Deploy the billing service to staging in three steps."),
    ).toBeInTheDocument()
  })

  it("lists versions newest first with tone, voice and length", async () => {
    serveDocument()
    await openDocument()

    await screen.findByRole("button", { name: "Teacher · af_heart · 6:18" })
    const versions = screen.getByRole("list", { name: "Versions" })
    const labels = within(versions)
      .getAllByRole("button")
      .map((button) => button.textContent)

    expect(labels).toEqual([
      "Podcast · bm_george · 5:41",
      "Teacher · af_heart · 6:18",
    ])
    expect(versionButton("Podcast · bm_george · 5:41")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("shows the script of the selected version", async () => {
    serveDocument()
    const user = await openDocument()

    expect(await screen.findByText("The podcast script.")).toBeInTheDocument()
    await user.click(versionButton("Teacher · af_heart · 6:18"))

    expect(await screen.findByText("The teacher script.")).toBeInTheDocument()
    expect(screen.queryByText("The podcast script.")).toBeNull()
  })

  it("explains why a version stayed WAV", async () => {
    serveDocument()
    await openDocument()

    expect(
      await screen.findByText(
        "ffmpeg is not installed, so this audio stayed WAV.",
      ),
    ).toBeInTheDocument()
  })

  it("plays the selected version in the player bar", async () => {
    serveDocument()
    const user = await openDocument()

    await user.click(
      await screen.findByRole("button", { name: `Play ${TITLE}` }),
    )

    const player = await screen.findByRole("region", { name: "Player" })
    expect(within(player).getByText("Podcast · bm_george")).toBeInTheDocument()
  })

  it("says in text when the document changed since its last audio", async () => {
    serveDocument({
      versions: [
        makeVersion({ id: 2, number: 2 }),
        makeVersion({ id: 1, number: 1 }),
      ],
    })
    await openDocument()

    expect(
      await screen.findByText(/changed since its last audio/),
    ).toBeInTheDocument()
  })

  it("says when a document has no audio yet", async () => {
    serveDocument({ audio: [] })
    await openDocument()

    expect(await screen.findByText(/No audio yet/)).toBeInTheDocument()
  })

  it("shows the step a version is at while it is being made", async () => {
    serveDocument({
      audio: [
        makeAudio({
          id: 9,
          tone: "teacher",
          status: "running",
          stage: "narrating",
          script: null,
          duration_seconds: null,
        }),
      ],
    })
    await openDocument()

    await waitFor(() =>
      expect(screen.getAllByText("Narrating").length).toBeGreaterThan(0),
    )
  })

  it("says when the document does not exist", async () => {
    serveDocument()
    renderAppAt("/docs/404")

    expect(
      await screen.findByRole("heading", { name: "Document not found" }),
    ).toBeInTheDocument()
  })

  it("treats an invalid id as not found without calling the server", async () => {
    serveDocument()
    renderAppAt("/docs/abc")

    expect(
      await screen.findByRole("heading", { name: "Document not found" }),
    ).toBeInTheDocument()
  })
})
