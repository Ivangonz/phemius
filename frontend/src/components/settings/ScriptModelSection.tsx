import { ScriptModelForm } from "./ScriptModelForm"
import { SettingsSection } from "./SettingsSection"

export function ScriptModelSection() {
  return (
    <SettingsSection
      id="script-model-heading"
      title="Script model"
      description="Categorizes documents and rewrites them so they sound right read aloud."
    >
      {(overview) => <ScriptModelForm overview={overview} />}
    </SettingsSection>
  )
}
