type VoicePreviewButtonProps = {
  label: string
  isActive: boolean
  onToggle: () => void
}

const PLAY_PATH = "M8 5v14l11-7z"
const STOP_PATH = "M6 6h12v12H6z"

export function VoicePreviewButton({
  label,
  isActive,
  onToggle,
}: VoicePreviewButtonProps) {
  const verb = isActive ? "Stop" : "Preview"
  const accessibleName = isActive
    ? `Stop preview of ${label}`
    : `Preview ${label}`

  return (
    <button
      type="button"
      aria-label={accessibleName}
      onClick={onToggle}
      className="inline-flex min-h-11 min-w-11 flex-none cursor-pointer items-center justify-center gap-1.5 rounded-control border border-line-control bg-surface px-3 text-secondary font-medium text-ink hover:bg-surface-subtle"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="currentColor"
        aria-hidden="true"
      >
        <path d={isActive ? STOP_PATH : PLAY_PATH} />
      </svg>
      {verb}
    </button>
  )
}
