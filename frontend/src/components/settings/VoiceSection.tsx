import { SettingsSection } from "./SettingsSection"
import { VoiceEngineForm } from "./VoiceEngineForm"

export function VoiceSection() {
  return (
    <SettingsSection
      id="voice-heading"
      title="Voice"
      description="Local engines run on this computer, so nothing is uploaded and there is no per-minute cost."
    >
      {(overview) => <VoiceEngineForm overview={overview} />}
    </SettingsSection>
  )
}
