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
      ...overrides.values,
    },
    secrets: {
      openrouter_api_key: { has_key: true, source: "saved", is_locked: false },
      openai_api_key: noKey,
      script_api_key: noKey,
      ...overrides.secrets,
    },
  }
}

export const settingsHandler = (overview = settingsOverview()) =>
  http.get("/api/settings", () => HttpResponse.json(overview))
