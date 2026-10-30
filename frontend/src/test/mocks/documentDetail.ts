import { http, HttpResponse } from "msw"
import type { components } from "@/lib/api-schema"
import { makeAudio } from "@/test/factories"

type Document = components["schemas"]["Document"]
type VersionSummary = components["schemas"]["VersionSummary"]
type Audio = components["schemas"]["Audio"]
type AudioSummary = components["schemas"]["AudioSummary"]
type AudioRequest = components["schemas"]["AudioRequest"]
type Job = components["schemas"]["Job"]

export type DocumentFixture = {
  document: Document
  versions: VersionSummary[]
  audio: Audio[]
  jobs?: Job[]
}

// Queues audio for the latest text the way the backend does, so the new
// version shows up on the next versions request.
function queueAudio(fixture: DocumentFixture, request: AudioRequest) {
  const id = Math.max(0, ...fixture.audio.map((audio) => audio.id)) + 1
  const audio = makeAudio({
    id,
    tone: request.tone ?? fixture.document.suggested_tone,
    voice: request.voice ?? null,
    version_id: fixture.document.version_id,
    created: Math.max(0, ...fixture.audio.map((item) => item.created)) + 1,
    status: "queued",
    stage: "writing_script",
    script: null,
    duration_seconds: null,
  })
  fixture.audio.push(audio)
  return { audio_id: audio.id, job_id: audio.job_id }
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
    http.post<{ documentId: string }, AudioRequest>(
      "/api/docs/:documentId/audio",
      async ({ params, request }) => {
        const fixture = findFixture(params.documentId)
        if (!fixture) return notFound()
        return HttpResponse.json(queueAudio(fixture, await request.json()))
      },
    ),
    http.get("/api/queue", () => {
      const items = getFixture().jobs ?? []
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 100,
        offset: 0,
        is_paused: false,
      })
    }),
  ]
}
