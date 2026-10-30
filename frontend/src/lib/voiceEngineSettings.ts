import { z } from "zod"
import type { components } from "./api-schema"
import {
  isLocked,
  savedValue,
  type ProviderOption,
  type SettingsOverview,
  type SettingsUpdate,
} from "./scriptModelSettings"

type AudioFormat = components["schemas"]["AudioFormat"]
export type VoiceSecretKey = "openai_speech_api_key" | "elevenlabs_api_key"
type VoiceFieldKey =
  "openai_speech_base_url" | "openai_speech_model" | VoiceSecretKey

export type VoiceEngineOption = ProviderOption & {
  fields: VoiceFieldKey[]
  keyField?: VoiceSecretKey
  isKeyRequired?: boolean
}

export const VOICE_ENGINES: VoiceEngineOption[] = [
  {
    id: "kokoro",
    label: "Kokoro",
    tag: "Local",
    description: "Free, runs on this computer.",
    fields: [],
  },
  {
    id: "piper",
    label: "Piper",
    tag: "Local",
    description: "Free, lighter and faster on small machines.",
    fields: [],
  },
  {
    id: "openai_speech",
    label: "OpenAI-compatible speech",
    tag: "Your server",
    description: "A speech endpoint you run or pay for.",
    fields: [
      "openai_speech_base_url",
      "openai_speech_api_key",
      "openai_speech_model",
    ],
    keyField: "openai_speech_api_key",
  },
  {
    id: "elevenlabs",
    label: "ElevenLabs",
    tag: "Cloud",
    description: "Hosted voices, paid per character.",
    fields: ["elevenlabs_api_key"],
    keyField: "elevenlabs_api_key",
    isKeyRequired: true,
  },
]

export const AUDIO_FORMATS = [
  { id: "wav", label: "WAV (no extra tools)", needsFfmpeg: false },
  { id: "m4a", label: "M4A (needs ffmpeg)", needsFfmpeg: true },
  { id: "mp3", label: "MP3 (needs ffmpeg)", needsFfmpeg: true },
] as const satisfies readonly {
  id: AudioFormat
  label: string
  needsFfmpeg: boolean
}[]

export function findVoiceEngine(id: string): VoiceEngineOption | undefined {
  return VOICE_ENGINES.find((engine) => engine.id === id)
}

const formShape = z.object({
  voice_engine: z.string(),
  openai_speech_base_url: z.string().trim(),
  openai_speech_model: z.string().trim(),
  openai_speech_api_key: z.string().trim(),
  elevenlabs_api_key: z.string().trim(),
  output_format: z.enum(["wav", "m4a", "mp3"]),
})

export type VoiceEngineFormValues = z.infer<typeof formShape>

const URL_PATTERN = /^https?:\/\/\S+$/

// Only the selected engine's fields are checked; the others keep whatever was
// typed in case the user switches back.
export function voiceEngineFormSchema(overview: SettingsOverview) {
  return formShape.superRefine((values, context) => {
    const engine = findVoiceEngine(values.voice_engine)
    const has = (field: VoiceFieldKey) => engine?.fields.includes(field)
    const fail = (field: VoiceFieldKey, message: string) => {
      if (!isLocked(overview, field))
        context.addIssue({ code: "custom", path: [field], message })
    }
    if (has("openai_speech_base_url"))
      if (!URL_PATTERN.test(values.openai_speech_base_url))
        fail(
          "openai_speech_base_url",
          "Enter an address starting with http:// or https://.",
        )
    if (has("openai_speech_model") && !values.openai_speech_model)
      fail("openai_speech_model", "Enter a model name.")
    const keyField = engine?.keyField
    if (keyField && engine.isKeyRequired && !values[keyField])
      if (!overview.secrets[keyField]?.has_key)
        fail(keyField, "Enter an API key.")
  })
}

export function toVoiceFormValues(
  overview: SettingsOverview,
): VoiceEngineFormValues {
  const format = savedValue(overview, "output_format")
  return {
    voice_engine: savedValue(overview, "voice_engine"),
    openai_speech_base_url: savedValue(overview, "openai_speech_base_url"),
    openai_speech_model: savedValue(overview, "openai_speech_model"),
    openai_speech_api_key: "",
    elevenlabs_api_key: "",
    output_format: format === "m4a" || format === "mp3" ? format : "wav",
  }
}

// Sends only what changed for the selected engine, never a locked field, and
// a key only when a new one was typed.
export function buildVoicePatch(
  values: VoiceEngineFormValues,
  overview: SettingsOverview,
): SettingsUpdate {
  const saved = toVoiceFormValues(overview)
  const engine = findVoiceEngine(values.voice_engine)
  const keys = [
    "voice_engine",
    ...(engine?.fields ?? []),
    "output_format",
  ] as const
  const patch: Record<string, string> = {}
  for (const key of keys) {
    const value = values[key]
    if (value !== saved[key] && value !== "" && !isLocked(overview, key))
      patch[key] = value
  }
  return patch
}
