import { useFormContext, useWatch } from "react-hook-form"
import {
  isLocked,
  savedValue,
  type SettingsOverview,
} from "@/lib/scriptModelSettings"
import {
  findVoiceEngine,
  type VoiceEngineFormValues,
} from "@/lib/voiceEngineSettings"
import { SecretField } from "./SecretField"
import { TextSettingField } from "./TextSettingField"

type VoiceEngineFieldsProps = { overview: SettingsOverview }

const KEY_LABELS = {
  openai_speech_api_key: "Speech server API key",
  elevenlabs_api_key: "ElevenLabs API key",
}

const KEY_MOVING_NOTE =
  "Warning: the saved key will be sent to this new address. Replace the key if it belongs to another server."

export function VoiceEngineFields({ overview }: VoiceEngineFieldsProps) {
  const { control } = useFormContext<VoiceEngineFormValues>()
  const [engineId, baseUrl] = useWatch({
    control,
    name: ["voice_engine", "openai_speech_base_url"],
  })
  const engine = findVoiceEngine(engineId)
  if (!engine) return null
  const has = (field: string) => engine.fields.some((item) => item === field)
  const keyField = engine.keyField
  // Until #85 is fixed, a saved key follows a changed base URL to the new host.
  const isKeyMoving =
    engine.id === "openai_speech" &&
    overview.secrets.openai_speech_api_key?.has_key === true &&
    baseUrl.trim() !== savedValue(overview, "openai_speech_base_url")

  return (
    <div className="flex flex-col gap-4.5">
      {has("openai_speech_base_url") && (
        <TextSettingField
          name="openai_speech_base_url"
          label="Speech server address"
          isLocked={isLocked(overview, "openai_speech_base_url")}
          placeholder="https://api.openai.com/v1"
          description={isKeyMoving ? KEY_MOVING_NOTE : undefined}
        />
      )}
      {keyField && (
        <SecretField
          name={keyField}
          label={KEY_LABELS[keyField]}
          status={overview.secrets[keyField]}
          isOptional={!engine.isKeyRequired}
        />
      )}
      {has("openai_speech_model") && (
        <TextSettingField
          name="openai_speech_model"
          label="Speech model"
          isLocked={isLocked(overview, "openai_speech_model")}
          placeholder="tts-1"
        />
      )}
      {engine.fields.length === 0 && (
        <p className="text-secondary text-muted">
          No key or server needed. Speech is made on this computer, so nothing
          is uploaded.
        </p>
      )}
    </div>
  )
}
