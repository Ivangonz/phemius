import type { components } from "@/lib/api-schema"

type DocumentListItem = components["schemas"]["DocumentListItem"]
type Job = components["schemas"]["Job"]

export function makeDocument(
  overrides: Partial<DocumentListItem> & Pick<DocumentListItem, "id" | "title">,
): DocumentListItem {
  const document: DocumentListItem = {
    source: `docs/${overrides.title.toLowerCase().replaceAll(" ", "-")}.md`,
    category: "how-to / tutorial",
    suggested_tone: "teacher",
    audio_suitability: "recommended",
    version: 1,
    created: 1_761_600_000 + overrides.id,
    updated: 1_761_600_000 + overrides.id,
    audio_id: null,
    format: null,
    size_bytes: null,
    status: "no_audio",
    stage: null,
    is_changed: false,
    signature: "",
    ...overrides,
  }
  return {
    ...document,
    signature: JSON.stringify({ ...document, signature: "" }),
  }
}

export function makeJob(
  overrides: Partial<Job> & { id: number; title: string },
): Job & { title: string } {
  return {
    type: "audio",
    state: "queued",
    stage: "writing_script",
    progress: 0,
    attempts: 0,
    document_id: overrides.id,
    audio_id: overrides.id + 100,
    version: 1,
    tone: "teacher",
    voice: "af_heart",
    error: null,
    hint: null,
    created: 1_761_600_000 + overrides.id,
    updated: 1_761_600_000 + overrides.id,
    started: null,
    finished: null,
    duration_seconds: null,
    cost_usd: null,
    input_tokens: null,
    output_tokens: null,
    ...overrides,
  }
}
