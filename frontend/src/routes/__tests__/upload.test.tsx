import { fireEvent, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import type { components } from "@/lib/api-schema"
import { makeDocument } from "@/test/factories"
import { documentsHandler } from "@/test/mocks/documents"
import { server } from "@/test/mocks/server"
import { renderAppAt } from "@/test/renderApp"

type DocumentListItem = components["schemas"]["DocumentListItem"]
type UploadResult = components["schemas"]["UploadResult"]

function file(name: string) {
  return new File(["# Notes\n\nSome text."], name, { type: "text/markdown" })
}

function serveUploads(
  respond: (name: string) => UploadResult,
  library: DocumentListItem[] = [],
) {
  let nextId = library.length + 1
  server.use(
    documentsHandler(() => library),
    http.post("/api/docs", async ({ request }) => {
      const [upload] = (await request.formData()).getAll("files")
      const name = upload instanceof File ? upload.name : "unknown"
      const result = respond(name)
      if (result.doc_id && !result.duplicate)
        library.push(makeDocument({ id: nextId++, title: name }))
      return HttpResponse.json([result])
    }),
  )
}

function uploads() {
  return screen.getByRole("region", { name: "Uploads" })
}

function upload(name: string) {
  return within(uploads()).getByRole("listitem", { name })
}

async function openLibrary() {
  const user = userEvent.setup()
  renderAppAt("/")
  await screen.findByRole("heading", { name: "Your library is empty" })
  return user
}

describe("uploading documents", () => {
  it("reports each chosen file and shows the new rows", async () => {
    serveUploads((name) => {
      if (name === "photo.png")
        return { file: name, error: "unsupported type .png" }
      if (name === "api.md")
        return { file: name, doc_id: 2, version: 1, is_audio_skipped: true }
      return { file: name, doc_id: 1, version: 1, duplicate: false }
    })
    const user = await openLibrary()

    await user.click(screen.getByRole("button", { name: "Upload documents" }))
    await user.upload(screen.getByLabelText("Choose documents to upload"), [
      file("notes.md"),
      file("photo.png"),
      file("api.md"),
    ])

    expect(
      await within(upload("api.md")).findByText("Added without audio"),
    ).toBeInTheDocument()
    expect(within(upload("notes.md")).getByText("Added")).toBeInTheDocument()
    expect(within(upload("photo.png")).getByText("Failed")).toBeInTheDocument()
    expect(
      within(upload("photo.png")).getByText("unsupported type .png"),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole("article", { name: "notes.md" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("article", { name: "api.md" })).toBeInTheDocument()
  })

  it("shows a file as uploading until the server answers", async () => {
    let finish = () => {}
    const answered = new Promise<void>((resolve) => (finish = resolve))
    server.use(
      http.post("/api/docs", async () => {
        await answered
        return HttpResponse.json([
          { file: "notes.md", doc_id: 1, version: 1, duplicate: true },
        ])
      }),
    )
    const user = await openLibrary()

    await user.upload(screen.getByLabelText("Choose documents to upload"), [
      file("notes.md"),
    ])

    expect(
      await within(upload("notes.md")).findByText("Uploading…"),
    ).toBeInTheDocument()
    finish()
    expect(
      await within(upload("notes.md")).findByText("Already in your library"),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Clear finished" }))
    expect(screen.queryByRole("region", { name: "Uploads" })).toBeNull()
  })

  it("uploads files dropped on the page", async () => {
    serveUploads((name) => ({ file: name, doc_id: 1, version: 1 }))
    await openLibrary()
    const heading = screen.getByRole("heading", { level: 1, name: "Library" })
    const dataTransfer = { types: ["Files"], files: [file("notes.md")] }

    fireEvent.dragEnter(heading, { dataTransfer })
    expect(
      screen.getByText("Drop files to add them to your library"),
    ).toBeInTheDocument()
    fireEvent.drop(heading, { dataTransfer })

    expect(
      screen.queryByText("Drop files to add them to your library"),
    ).toBeNull()
    expect(
      await within(upload("notes.md")).findByText("Added"),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole("article", { name: "notes.md" }),
    ).toBeInTheDocument()
  })

  it("shows the server's error and hint when an upload is refused", async () => {
    server.use(
      http.post("/api/docs", () =>
        HttpResponse.json(
          {
            detail: "The file is too large",
            code: "invalid_input",
            hint: "Upload files under 50 MB.",
          },
          { status: 413 },
        ),
      ),
    )
    const user = await openLibrary()

    await user.upload(screen.getByLabelText("Choose documents to upload"), [
      file("huge.pdf"),
    ])

    const item = upload("huge.pdf")
    expect(await within(item).findByText("Failed")).toBeInTheDocument()
    expect(within(item).getByText("The file is too large")).toBeInTheDocument()
    expect(
      within(item).getByText("Upload files under 50 MB."),
    ).toBeInTheDocument()
  })
})
