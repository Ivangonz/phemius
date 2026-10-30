import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"

type Document = components["schemas"]["Document"]
type VersionSummary = components["schemas"]["VersionSummary"]
type Audio = components["schemas"]["Audio"]
type AudioSummary = components["schemas"]["AudioSummary"]

export type DocumentFixture = {
  document: Document
  versions: VersionSummary[]
  audio: Audio[]
}

const notFound = () =>
  HttpResponse.json(
    { detail: "Document 404 not found", code: "not_found" },
    { status: 404 },
  )

function summarize(audio: Audio, version: VersionSummary): AudioSummary {
  const { id, tone, voice, job_id, status, stage, error, hint } = audio
  return {
    ...{ id, tone, voice, job_id, status, stage, error, hint },
    section_titles: audio.section_titles,
    version: version.number,
  }
}

function versionsWithAudio({ versions, audio }: DocumentFixture) {
  const newestFirst = [...audio].sort((a, b) => b.created - a.created)
  return versions.map((version) => ({
    ...version,
    audio: newestFirst
      .filter((item) => item.version_id === version.id)
      .map((item) => summarize(item, version)),
  }))
}

// Reads the fixture at request time so a test can change it between polls.
export function documentHandlers(getFixture: () => DocumentFixture) {
  const findFixture = (documentId: unknown) => {
    const fixture = getFixture()
    return String(fixture.document.id) === documentId ? fixture : undefined
  }

  return [
    http.get("/api/docs/:documentId", ({ params }) => {
      const fixture = findFixture(params.documentId)
      return fixture ? HttpResponse.json(fixture.document) : notFound()
    }),
    http.get("/api/docs/:documentId/versions", ({ params }) => {
      const fixture = findFixture(params.documentId)
      if (!fixture) return notFound()
      const items = versionsWithAudio(fixture)
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 25,
        offset: 0,
      })
    }),
    http.get("/api/audio/:audioId", ({ params }) => {
      const found = getFixture().audio.find(
        (item) => String(item.id) === params.audioId,
      )
      return found ? HttpResponse.json(found) : notFound()
    }),
  ]
}
