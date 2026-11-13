import { Button } from "@/components/ui/Button"
import type { VoiceView } from "@/hooks/useVoices"
import { getErrorMessage } from "@/lib/api"
import { downloadProgressText } from "@/lib/voiceDownload"

type VoiceInstallProps = {
  voice: VoiceView
  isStarting: boolean
  startError: Error | null
  onInstall: () => void
}

export function VoiceInstall({
  voice,
  isStarting,
  startError,
  onInstall,
}: VoiceInstallProps) {
  const download = voice.download
  if (voice.is_installed) return null

  if (download?.state === "downloading") {
    return (
      <div className="flex flex-col gap-1">
        <progress
          aria-label={`Downloading ${voice.label}`}
          value={download.total ? (download.done ?? 0) : undefined}
          max={download.total ?? undefined}
          className="h-2 w-full accent-primary"
        />
        <p className="text-secondary text-muted">
          {downloadProgressText(download)}
        </p>
      </div>
    )
  }

  const failure =
    download?.state === "failed"
      ? `Download failed: ${download.message ?? "unknown error"}`
      : startError && `Could not start: ${getErrorMessage(startError)}`

  return (
    <div className="flex flex-col items-start gap-1">
      {failure && (
        <p className="text-secondary font-semibold text-danger-ink">
          {failure}
        </p>
      )}
      {download?.hint && (
        <p className="text-secondary text-muted">{download.hint}</p>
      )}
      <Button variant="secondary" disabled={isStarting} onClick={onInstall}>
        {isStarting ? "Starting…" : "Install"}
        <span className="sr-only"> {voice.label}</span>
      </Button>
    </div>
  )
}
