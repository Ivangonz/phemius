import { Button } from "@/components/ui/Button"

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
  const accessibleName = isActive
    ? `Stop preview of ${label}`
    : `Preview ${label}`

  return (
    <Button
      variant="secondary"
      aria-label={accessibleName}
      onClick={onToggle}
      className="flex-none"
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
      {isActive ? "Stop" : "Preview"}
    </Button>
  )
}
