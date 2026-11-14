import { Button } from "@/components/ui/Button"
import type { VoiceView } from "@/hooks/useVoices"
import { ApiError, getErrorMessage } from "@/lib/api"
import { InstallButtonText } from "./InstallButtonText"
import { VoiceDownloadProgress } from "./VoiceDownloadProgress"

type VoiceInstallProps = {
  voice: VoiceView
  isStarting: boolean
  startError: Error | null
  waitsFor: string | null
  onInstall: () => void
}

// A start error is newer than a failed download shown by the list: it is
// cleared whenever the list shows this voice downloading again.
function failureNotes(voice: VoiceView, startError: Error | null) {
  if (startError) {
    const hint = startError instanceof ApiError ? startError.hint : undefined
    return { text: `Could not start: ${getErrorMessage(startError)}`, hint }
  }
  const download = voice.download
  if (download?.state !== "failed") return null
  const reason = download.message ?? "unknown error"
  return { text: `Download failed: ${reason}`, hint: download.hint }
}

// The button stays in place while installing so keyboard focus is not lost;
// aria-disabled keeps it focusable where `disabled` would drop focus.
export function VoiceInstall({
  voice,
  isStarting,
  startError,
  waitsFor,
  onInstall,
}: VoiceInstallProps) {
  if (voice.is_installed) return null
  const download = voice.download
  const isDownloading = download?.state === "downloading"
  const isUnderway = isStarting || isDownloading
  const isBlocked = isUnderway || waitsFor !== null
  const failure = isUnderway ? null : failureNotes(voice, startError)

  return (
    <div className="flex flex-col items-start gap-1">
      {isDownloading && (
        <VoiceDownloadProgress label={voice.label} download={download} />
      )}
      {failure && (
        <p className="text-secondary font-semibold text-danger-ink">
          {failure.text}
        </p>
      )}
      {failure?.hint && (
        <p className="text-secondary text-muted">{failure.hint}</p>
      )}
      <Button
        variant="secondary"
        aria-disabled={isBlocked || undefined}
        onClick={() => !isBlocked && onInstall()}
        className="aria-disabled:cursor-not-allowed aria-disabled:text-muted"
      >
        <InstallButtonText
          label={voice.label}
          isUnderway={isUnderway}
          waitsFor={isUnderway ? null : waitsFor}
        />
      </Button>
    </div>
  )
}
