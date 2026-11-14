import type { VoiceView } from "@/hooks/useVoices"
import { formatBytes } from "./formatBytes"

export function installStateText(voice: VoiceView): string {
  if (voice.is_installed) return "Installed"
  if (voice.size_bytes === null) return "Not installed"
  return `Not installed · ${formatBytes(voice.size_bytes)}`
}

// "Default" follows the saved setting, not the radio a save is still waiting on.
export function voiceStateText(voice: VoiceView): string {
  const install = installStateText(voice)
  return voice.is_default ? `Default · ${install}` : install
}
