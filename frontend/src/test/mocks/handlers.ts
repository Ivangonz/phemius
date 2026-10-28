import { http, HttpResponse } from "msw"

export const libraryConfig = {
  tones: ["teacher", "narrator"],
  voices: { af_heart: "Heart" },
  default_voice: "af_heart",
  tts_status: { ok: true },
  watch_dir: null,
  llm: true,
  script_provider: "openrouter",
  model: "anthropic/claude-haiku-5.5",
  llm_error: null,
  tts: "kokoro",
}

export const handlers = [
  http.get("/api/config", () => HttpResponse.json(libraryConfig)),
]
