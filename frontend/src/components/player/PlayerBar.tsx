import { usePlayer } from "@/hooks/usePlayer"
import { SHORTCUTS } from "@/hooks/usePlayerShortcuts"
import { SKIP_BACK_SECONDS, SKIP_FORWARD_SECONDS } from "./playerContext"
import { PlayerControlButton } from "./PlayerControlButton"
import { PlayPauseButton } from "./PlayPauseButton"
import { SeekBar } from "./SeekBar"

function formatSpeed(rate: number): string {
  return Number.isInteger(rate * 10) ? rate.toFixed(1) : rate.toFixed(2)
}

export function PlayerBar() {
  const { track, isPlaying, hasError, playbackRate, toggle, skip, cycleSpeed } =
    usePlayer()
  if (!track) return null

  const speed = formatSpeed(playbackRate)

  return (
    <section
      aria-label="Player"
      className="sticky bottom-0 z-10 flex flex-wrap items-center gap-x-7 gap-y-3 border-t border-line bg-surface px-4 py-3 md:px-7 md:py-3.5"
    >
      <div className="flex min-w-0 flex-[1_1_240px] items-center gap-3.5">
        <PlayPauseButton isPlaying={isPlaying} onClick={toggle} />
        <div className="min-w-0">
          <div className="truncate font-semibold">{track.title}</div>
          {hasError ? (
            <div role="alert" className="mt-0.5 text-small text-danger-ink">
              This audio could not be loaded.
            </div>
          ) : (
            <div className="mt-0.5 truncate font-mono text-small text-muted">
              {track.meta}
            </div>
          )}
        </div>
      </div>
      <div className="order-last w-full md:order-none md:w-auto md:flex-[2_1_320px]">
        <SeekBar />
      </div>
      <div className="flex items-center gap-1.5">
        <PlayerControlButton
          aria-label={`Back ${SKIP_BACK_SECONDS} seconds`}
          aria-keyshortcuts={SHORTCUTS.back}
          onClick={() => skip(-SKIP_BACK_SECONDS)}
        >
          -{SKIP_BACK_SECONDS}
        </PlayerControlButton>
        <PlayerControlButton
          aria-label={`Forward ${SKIP_FORWARD_SECONDS} seconds`}
          aria-keyshortcuts={SHORTCUTS.forward}
          onClick={() => skip(SKIP_FORWARD_SECONDS)}
        >
          +{SKIP_FORWARD_SECONDS}
        </PlayerControlButton>
        <PlayerControlButton
          aria-label={`Playback speed ${speed} times`}
          onClick={cycleSpeed}
        >
          {speed}x
        </PlayerControlButton>
      </div>
    </section>
  )
}
