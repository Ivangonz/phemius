import { http, HttpResponse } from "msw"
import type { SettingsOverview } from "@/hooks/useSettings"
import type { components } from "@/lib/api-schema"

type SettingStatus = components["schemas"]["SettingStatus"]
type SecretStatus = components["schemas"]["SecretStatus"]

const saved = (value: SettingStatus["value"]): SettingStatus => ({
  value,
  source: "saved",
  is_locked: false,
})

const noKey: SecretStatus = {
  has_key: false,
  source: "default",
  is_locked: false,
}

// OpenRouter with a saved key, as most installs start.
export function settingsOverview(
  overrides: {
    values?: Record<string, SettingStatus>
    secrets?: Record<string, SecretStatus>
  } = {},
): SettingsOverview {
  return {
    values: {
      script_provider: saved("openrouter"),
      model: saved("anthropic/claude-haiku-5.5"),
      ollama_url: saved("http://localhost:11434"),
      ollama_model: saved("llama3.2"),
      script_base_url: saved(null),
      script_max_tokens: saved(8000),
      access_mode: { value: "local", source: "default", is_locked: false },
      voice_engine: saved("kokoro"),
      openai_speech_base_url: saved("https://api.openai.com/v1"),
      openai_speech_model: saved("tts-1"),
      output_format: saved("wav"),
      ...overrides.values,
    },
    secrets: {
      openrouter_api_key: { has_key: true, source: "saved", is_locked: false },
      openai_api_key: noKey,
      script_api_key: noKey,
      openai_speech_api_key: noKey,
      elevenlabs_api_key: noKey,
      ...overrides.secrets,
    },
  }
}

export const settingsHandler = (overview = settingsOverview()) =>
  http.get("/api/settings", () => HttpResponse.json(overview))

type Overrides = Parameters<typeof settingsOverview>[0]

// Answers PATCH like the server: the saved values come back in the overview.
export function serveSettingsSaving(patches: unknown[], base: Overrides = {}) {
  let overview = settingsOverview(base)
  return [
    http.get("/api/settings", () => HttpResponse.json(overview)),
    http.patch("/api/settings", async ({ request }) => {
      const patch = (await request.json()) as Record<string, string | number>
      patches.push(patch)
      overview = settingsOverview({
        ...base,
        values: {
          ...base.values,
          ...Object.fromEntries(
            Object.entries(patch).map(([key, value]) => [key, saved(value)]),
          ),
        },
      })
      return HttpResponse.json(overview)
    }),
  ]
}
