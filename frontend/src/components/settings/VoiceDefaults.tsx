import {
  isLocked,
  savedValue,
  type SettingsOverview,
} from "@/lib/settingsFields"
import { findVoiceEngine } from "@/lib/voiceEngineSettings"
import { DefaultToneField } from "./DefaultToneField"
import { VoiceList } from "./VoiceList"

type VoiceDefaultsProps = { overview: SettingsOverview }

// The list shows the saved engine's voices, so an unsaved engine choice
// above does not change it until Save.
export function VoiceDefaults({ overview }: VoiceDefaultsProps) {
  const engineId = savedValue(overview, "voice_engine")
  const engineLabel = findVoiceEngine(engineId)?.label ?? engineId

  return (
    <div className="flex flex-col gap-4.5 border-t border-line pt-4.5">
      <VoiceList
        engineLabel={engineLabel}
        isLocked={isLocked(overview, "default_voice")}
      />
      <DefaultToneField
        overview={overview}
        isLocked={isLocked(overview, "default_tone")}
      />
    </div>
  )
}
