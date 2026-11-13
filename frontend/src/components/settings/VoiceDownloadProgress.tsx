import { useId } from "react"
import type { components } from "@/lib/api-schema"
import { downloadProgressText } from "@/lib/voiceDownload"

type VoiceDownloadProgressProps = {
  label: string
  download: components["schemas"]["DownloadProgress"]
}

export function VoiceDownloadProgress({
  label,
  download,
}: VoiceDownloadProgressProps) {
  const textId = useId()
  const text = downloadProgressText(download)
  const isMeasured = Boolean(download.total)

  return (
    <div className="flex w-full flex-col gap-1">
      <progress
        aria-label={`Downloading ${label}`}
        aria-valuetext={text}
        aria-describedby={textId}
        value={isMeasured ? (download.done ?? 0) : undefined}
        max={isMeasured ? (download.total ?? undefined) : undefined}
        className="h-2 w-full accent-primary"
      />
      <p id={textId} className="text-secondary text-muted">
        {text}
      </p>
    </div>
  )
}
