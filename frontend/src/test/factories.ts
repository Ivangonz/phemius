import type { components } from "@/lib/api-schema"

type DocumentListItem = components["schemas"]["DocumentListItem"]

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
