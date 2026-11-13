import type { PreviewState } from "@/hooks/useVoicePreview"
import { getErrorMessage } from "@/lib/api"

type VoiceListStatusProps = {
  saveError: Error | null
  isRefreshFailed: boolean
  preview: PreviewState
  labelOf: (voiceId: string) => string
}

function previewText(preview: PreviewState, labelOf: (id: string) => string) {
  if (!preview) return null
  const label = labelOf(preview.voiceId)
  if (preview.status === "failed") return `Preview failed: ${preview.message}`
  if (preview.status === "loading") return `Preparing a preview of ${label}…`
  return `Playing a preview of ${label}.`
}

// One live region for saving the default and for previews.
export function VoiceListStatus({
  saveError,
  isRefreshFailed,
  preview,
  labelOf,
}: VoiceListStatusProps) {
  const isPreviewFailed = preview?.status === "failed"

  return (
    <div role="status" className="flex flex-col gap-0.5 text-secondary">
      {saveError && (
        <p className="font-semibold text-danger-ink">
          Not saved: {getErrorMessage(saveError)}
        </p>
      )}
      {isRefreshFailed && (
        <p className="text-muted">
          Could not refresh the voice list; showing the last one loaded.
        </p>
      )}
      <p className={isPreviewFailed ? "font-semibold text-danger-ink" : ""}>
        {previewText(preview, labelOf)}
      </p>
    </div>
  )
}
