import { memo } from "react"
import { useAudio } from "@/hooks/useAudio"
import { describeVersion, type AudioVersion } from "@/lib/audioVersions"
import { describeJob } from "@/lib/documentStatus"
import { formatTime } from "@/lib/formatTime"

type VersionButtonProps = {
  version: AudioVersion
  isSelected: boolean
  onSelect: (audioId: number) => void
}

const SELECTED_CLASSES = "border-ink bg-ink text-white"
const IDLE_CLASSES = "border-line-control bg-surface hover:bg-surface-subtle"

function useVersionDetailLabel(version: AudioVersion): string | null {
  const { data: audio } = useAudio(version.id)
  if (version.status !== "done") return describeJob(version).label
  if (audio?.duration_seconds == null) return null
  return formatTime(audio.duration_seconds)
}

export const VersionButton = memo(function VersionButton({
  version,
  isSelected,
  onSelect,
}: VersionButtonProps) {
  const detail = useVersionDetailLabel(version)
  const label = detail
    ? `${describeVersion(version)} · ${detail}`
    : describeVersion(version)

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      onClick={() => onSelect(version.id)}
      className={`min-h-11 cursor-pointer rounded-control border px-4 font-medium transition-colors ${isSelected ? SELECTED_CLASSES : IDLE_CLASSES}`}
    >
      {label}
    </button>
  )
})
