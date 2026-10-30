import type { components } from "@/lib/api-schema"

type DocumentListItem = components["schemas"]["DocumentListItem"]
type Job = components["schemas"]["Job"]
type Document = components["schemas"]["Document"]
type VersionSummary = components["schemas"]["VersionSummary"]
type Audio = components["schemas"]["Audio"]

const DESCRIBED = {
  category: "how-to / tutorial",
  summary: "Deploy the billing service to staging in three steps.",
  suggested_tone: "teacher",
  tone_rationale: "It reads as a step-by-step how-to.",
  audio_suitability: "recommended",
  suitability_reason: null,
  suitability_source: null,
  content_hash: "hash",
} as const

export function makeDocumentDetail(
  overrides: Partial<Document> & Pick<Document, "id" | "title">,
): Document {
  return {
    ...DESCRIBED,
    version_id: 1,
    version: 1,
    source: "github: acme/billing · docs/deploy-guide.md",
    source_id: null,
    text: "The original text.",
    created: 1_761_600_000,
    ...overrides,
  }
}

export function makeVersion(
  overrides: Partial<VersionSummary> & Pick<VersionSummary, "id" | "number">,
): VersionSummary {
  return {
    ...DESCRIBED,
    title: "Deploying the Billing Service",
    created: 1_761_600_000 + overrides.number,
    audio: [],
    ...overrides,
  }
}

export function makeAudio(
  overrides: Partial<Audio> & Pick<Audio, "id" | "tone">,
): Audio {
  return {
    doc_id: 1,
    version_id: 1,
    voice: "kokoro:af_heart",
    script: `The ${overrides.tone} script.`,
    path: `audio/${overrides.id}.m4a`,
    format: "m4a",
    size_bytes: 4_200_000,
    duration_seconds: 378,
    conversion_note: null,
    created: 1_761_700_000 + overrides.id,
    job_id: 100 + overrides.id,
    status: "done",
    stage: "converting",
    error: null,
    hint: null,
    section_titles: [],
    chapters: [],
    ...overrides,
  }
}

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

type SourceView = components["schemas"]["SourceView"]

export function makeSource(
  overrides: Partial<SourceView> & Pick<SourceView, "id" | "name">,
): SourceView {
  return {
    kind: "folder",
    config: { path: `/home/me/${overrides.name}` },
    status: "active",
    last_sync: 1_761_600_000,
    error: null,
    created: 1_761_600_000,
    updated: 1_761_600_000,
    rules: {},
    effective_rules: {
      auto_audio: true,
      file_types: [".md", ".txt"],
      keep_versions: true,
      regenerate_on_change: false,
      skip_not_recommended: true,
    },
    is_locked: false,
    ...overrides,
  }
}
