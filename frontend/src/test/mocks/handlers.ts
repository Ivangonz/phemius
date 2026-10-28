import { http, HttpResponse } from "msw"
import type { LibraryConfig } from "@/hooks/useLibraryConfig"

export const libraryConfig: LibraryConfig = {
  tones: { teacher: "Patient and structured." },
  voices: { "kokoro:af_heart": "Heart" },
  default_voice: "af_heart",
  tts_status: { is_ready: true, message: "Kokoro is ready." },
  watch_dir: null,
  llm: true,
  script_provider: "openrouter",
  model: "anthropic/claude-haiku-5.5",
  llm_error: null,
  llm_hint: null,
  tts: "kokoro",
  ffmpeg: {
    is_present: false,
    version: null,
    status: "optional",
    message: "ffmpeg is not installed; audio stays WAV.",
  },
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
