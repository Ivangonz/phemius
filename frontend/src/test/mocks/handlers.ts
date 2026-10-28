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
  http.get("/api/audio/:audioId/url", ({ params }) =>
    HttpResponse.json({
      url: `/api/audio/${String(params.audioId)}/file`,
      expires: 1_900_000_000,
    }),
  ),
]
