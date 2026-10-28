import { usePlayer, usePlayerProgress } from "@/hooks/usePlayer"
import { formatTime } from "@/lib/formatTime"

export function SeekBar() {
  const { seek } = usePlayer()
  const { currentTime, duration } = usePlayerProgress()
  const elapsed = formatTime(currentTime)
  const total = formatTime(duration)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between gap-3 font-mono text-small text-muted">
        <span>{elapsed}</span>
        <span>{total}</span>
      </div>
      <input
        type="range"
        aria-label="Seek"
        aria-valuetext={`${elapsed} of ${total}`}
        min={0}
        max={duration}
        step={1}
        value={Math.min(currentTime, duration)}
        disabled={duration === 0}
        onChange={(event) => seek(event.currentTarget.valueAsNumber)}
        className="h-2 w-full cursor-pointer accent-primary disabled:cursor-default"
      />
    </div>
  )
}
