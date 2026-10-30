import { screen, within } from "@testing-library/react"
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

function serveDocument(overrides: Partial<DocumentFixture> = {}) {
  const fixture: DocumentFixture = {
    document: makeDocumentDetail({ id: 1, title: TITLE }),
    versions: [makeVersion({ id: 1, number: 1 })],
    audio: [teacher],
    ...overrides,
  }
  server.use(...documentHandlers(() => fixture))
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
