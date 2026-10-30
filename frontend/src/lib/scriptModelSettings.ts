import { z } from "zod"
import type { components } from "./api-schema"

export type SettingsOverview = components["schemas"]["SettingsOverview"]
export type SettingsUpdate = components["schemas"]["Settings"]

export type SecretKey =
  "openrouter_api_key" | "openai_api_key" | "script_api_key"
type ValueKey =
  | "model"
  | "ollama_url"
  | "ollama_model"
  | "script_base_url"
  | "script_max_tokens"
type FieldKey = ValueKey | SecretKey
export type ProviderTag = "Cloud" | "Your server" | "Local"

export type ProviderOption = {
  id: string
  label: string
  tag: ProviderTag
  description: string
}

export type Provider = ProviderOption & {
  fields: FieldKey[]
  keyField?: SecretKey
  isKeyRequired?: boolean
}

// The design's "Provider API key" card is the OpenAI preset: other vendors
// connect through their OpenAI-compatible endpoint as "your own server".
export const PROVIDERS: Provider[] = [
  {
    id: "openrouter",
    label: "OpenRouter",
    tag: "Cloud",
    description: "One key, many hosted models.",
    fields: ["openrouter_api_key", "model"],
    keyField: "openrouter_api_key",
    isKeyRequired: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    tag: "Cloud",
    description: "Your own OpenAI API key.",
    fields: ["openai_api_key", "model"],
    keyField: "openai_api_key",
    isKeyRequired: true,
  },
  {
    id: "openai_compatible",
    label: "OpenAI-compatible server",
    tag: "Your server",
    description:
      "LM Studio, vLLM, llama.cpp, a company gateway, or another vendor's OpenAI-compatible API.",
    fields: ["script_base_url", "script_api_key", "model"],
    keyField: "script_api_key",
  },
  {
    id: "ollama",
    label: "Ollama",
    tag: "Local",
    description: "Runs on this computer. Nothing leaves it.",
    fields: ["ollama_url", "ollama_model"],
  },
  {
    id: "offline",
    label: "Offline rules",
    tag: "Local",
    description: "No model. Simple rules tidy the text for reading aloud.",
    fields: [],
  },
]

export function findProvider(id: string | undefined): Provider | undefined {
  return PROVIDERS.find((provider) => provider.id === id)
}

const required = (label: string) => z.string().trim().min(1, `Enter ${label}.`)

export const scriptModelFormSchema = z.object({
  script_provider: z.string(),
  model: z.string().trim(),
  ollama_url: z.string().trim(),
  ollama_model: z.string().trim(),
  script_base_url: z.string().trim(),
  openrouter_api_key: z.string().trim(),
  openai_api_key: z.string().trim(),
  script_api_key: z.string().trim(),
  script_max_tokens: z
    .number({ error: "Enter a whole number of tokens." })
    .int("Enter a whole number of tokens.")
    .positive("Enter a number above zero."),
})

export type ScriptModelFormValues = z.infer<typeof scriptModelFormSchema>

const FIELD_RULES: Partial<Record<FieldKey, z.ZodType>> = {
  model: required("a model name"),
  ollama_url: required("the Ollama address"),
  ollama_model: required("an Ollama model"),
  script_base_url: z
    .string()
    .trim()
    .regex(
      /^https?:\/\/\S+$/,
      "Enter an address starting with http:// or https://.",
    ),
}

// Only the selected provider's fields are checked; the others keep whatever
// was typed in case the user switches back.
export function validateProviderFields(
  values: ScriptModelFormValues,
  overview: SettingsOverview,
): Partial<Record<FieldKey, string>> {
  const provider = findProvider(values.script_provider)
  const errors: Partial<Record<FieldKey, string>> = {}
  for (const field of provider?.fields ?? []) {
    const result = FIELD_RULES[field]?.safeParse(values[field])
    if (result && !result.success && !isLocked(overview, field))
      errors[field] = result.error.issues[0]?.message
  }
  const keyField = provider?.keyField
  if (keyField && provider.isKeyRequired && !values[keyField])
    if (!overview.secrets[keyField]?.has_key)
      errors[keyField] = "Enter an API key."
  return errors
}

export function isLocked(overview: SettingsOverview, key: string): boolean {
  return (
    overview.values[key]?.is_locked ?? overview.secrets[key]?.is_locked ?? false
  )
}

export function savedValue(overview: SettingsOverview, key: string): string {
  const value = overview.values[key]?.value
  return value === null || value === undefined ? "" : String(value)
}

export function toFormValues(
  overview: SettingsOverview,
): ScriptModelFormValues {
  return {
    script_provider: savedValue(overview, "script_provider"),
    model: savedValue(overview, "model"),
    ollama_url: savedValue(overview, "ollama_url"),
    ollama_model: savedValue(overview, "ollama_model"),
    script_base_url: savedValue(overview, "script_base_url"),
    openrouter_api_key: "",
    openai_api_key: "",
    script_api_key: "",
    script_max_tokens: Number(overview.values.script_max_tokens?.value ?? 8000),
  }
}

// Sends only what changed for the selected provider, never a locked field,
// and a key only when a new one was typed.
export function buildSettingsPatch(
  values: ScriptModelFormValues,
  overview: SettingsOverview,
): SettingsUpdate {
  const saved = toFormValues(overview)
  const provider = findProvider(values.script_provider)
  const keys: FieldKey[] = [...(provider?.fields ?? []), "script_max_tokens"]
  const patch: Record<string, string | number> = {}
  if (values.script_provider !== saved.script_provider)
    patch.script_provider = values.script_provider
  for (const key of keys) {
    const value = values[key]
    if (value !== saved[key] && value !== "" && !isLocked(overview, key))
      patch[key] = value
  }
  if ("script_provider" in patch && isLocked(overview, "script_provider"))
    delete patch.script_provider
  return patch
}
