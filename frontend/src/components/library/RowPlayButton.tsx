import { usePlayer } from "@/hooks/usePlayer"
import type { Track } from "@/components/player/playerContext"

const CURRENT_CLASSES =
  "border-primary bg-primary text-white hover:bg-primary-hover"
const IDLE_CLASSES =
  "border-line-control bg-surface text-primary hover:bg-primary-tint"

export function RowPlayButton({ track }: { track: Track }) {
  const player = usePlayer()
  const isCurrent = player.track?.audioId === track.audioId
  const isPlaying = isCurrent && player.isPlaying
  const action = isPlaying ? "Pause" : "Play"
  const variant = isCurrent ? CURRENT_CLASSES : IDLE_CLASSES

  function handleClick() {
    if (isCurrent) player.toggle()
    else player.play(track)
  }

  return (
    <button
      type="button"
      aria-label={`${action} ${track.title}`}
      onClick={handleClick}
      className={`inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border transition-colors ${variant}`}
    >
      <svg
        width="16"
        height="16"
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
