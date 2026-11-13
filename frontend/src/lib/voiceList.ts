import type { VoiceView } from "@/hooks/useVoices"
import { formatBytes } from "./formatBytes"

export function installStateText(voice: VoiceView): string {
  if (voice.is_installed) return "Installed"
  if (voice.size_bytes === null) return "Not installed"
  return `Not installed · ${formatBytes(voice.size_bytes)}`
}

export function voiceStateText(voice: VoiceView, isDefault: boolean): string {
  const install = installStateText(voice)
  return isDefault ? `Default · ${install}` : install
}
