import { http, HttpResponse } from "msw"
import type { VoiceView } from "@/hooks/useVoices"

export function makeVoice(
  overrides: Partial<VoiceView> & Pick<VoiceView, "id" | "label">,
): VoiceView {
  return {
    accent: "American English, female",
    is_installed: true,
    size_bytes: null,
    license: "Apache-2.0",
    is_default: false,
    download: null,
    ...overrides,
  }
}

export const kokoroVoices: VoiceView[] = [
  makeVoice({ id: "kokoro:af_heart", label: "Heart", is_default: true }),
  makeVoice({ id: "kokoro:af_bella", label: "Bella" }),
  makeVoice({
    id: "kokoro:bm_george",
    label: "George",
    accent: "British English, male",
    is_installed: false,
    size_bytes: 82_000_000,
  }),
]

export function voicesPage(items: VoiceView[]) {
  return { items, total: items.length, limit: 100, offset: 0 }
}

export const voicesHandler = (voices: () => VoiceView[] = () => kokoroVoices) =>
  http.get("/api/voices", () => HttpResponse.json(voicesPage(voices())))
