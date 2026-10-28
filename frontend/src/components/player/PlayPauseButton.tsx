import { SHORTCUTS } from "@/hooks/usePlayerShortcuts"

type PlayPauseButtonProps = {
  isPlaying: boolean
  onClick: () => void
}

export function PlayPauseButton({ isPlaying, onClick }: PlayPauseButtonProps) {
  return (
    <button
      type="button"
      aria-label={isPlaying ? "Pause" : "Play"}
      aria-keyshortcuts={SHORTCUTS.toggle}
      onClick={onClick}
      className="inline-flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-full bg-primary text-white transition-colors hover:bg-primary-hover"
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="currentColor"
        aria-hidden="true"
      >
        {isPlaying ? (
          <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" />
        ) : (
          <path d="M8 5v14l11-7z" />
        )}
      </svg>
    </button>
  )
}
