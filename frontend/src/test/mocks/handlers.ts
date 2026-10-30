import { http, HttpResponse } from "msw"
import type { AccessStatus } from "@/hooks/useAccess"
import type { LibraryConfig } from "@/hooks/useLibraryConfig"
import { healthyChecks, makeCheckRun, serveChecks } from "./checks"
import { documentsHandler } from "./documents"
import { queueHandlers, quietDay, todayStatsHandler } from "./queue"
import { settingsHandler } from "./settings"

export const libraryConfig: LibraryConfig = {
  tones: { teacher: "Patient and structured.", executive: "Concise." },
  voices: { "kokoro:af_heart": "Heart" },
  default_voice: "af_heart",
  tts_status: { is_ready: true, message: "Kokoro is ready." },
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

export const accessStatus: AccessStatus = {
  active_mode: "local",
  is_token_required: false,
  has_token: false,
  is_token_from_env: false,
  port: 8000,
}

export const handlers = [
  http.get("/api/access", () => HttpResponse.json(accessStatus)),
  http.get("/api/config", () => HttpResponse.json(libraryConfig)),
  http.get("/api/audio/:audioId/url", ({ params }) =>
    HttpResponse.json({
      url: `/api/audio/${String(params.audioId)}/file`,
      expires: 1_900_000_000,
    }),
  ),
  documentsHandler(() => []),
  ...queueHandlers({ jobs: [], isPaused: false }),
  todayStatsHandler(() => quietDay),
  ...serveChecks({
    lastRun: makeCheckRun(healthyChecks),
    runs: [makeCheckRun(healthyChecks)],
  }).handlers,
  settingsHandler(),
]
