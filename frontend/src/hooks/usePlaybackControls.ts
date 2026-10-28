import { useCallback, useState, type RefObject } from "react"

const SPEEDS = [1, 1.25, 1.5, 2, 0.75]

// Seeking and speed act on the audio element directly; only the speed is state.
export function usePlaybackControls(
  audioRef: RefObject<HTMLAudioElement | null>,
) {
  const [playbackRate, setPlaybackRate] = useState(1)

  const seek = useCallback(
    (seconds: number) => {
      const audio = audioRef.current
      if (!audio || !Number.isFinite(seconds)) return
      const end = Number.isFinite(audio.duration) ? audio.duration : seconds
      audio.currentTime = Math.min(Math.max(0, seconds), end)
    },
    [audioRef],
  )

  const skip = useCallback(
    (deltaSeconds: number) => {
      const audio = audioRef.current
      if (audio) seek(audio.currentTime + deltaSeconds)
    },
    [audioRef, seek],
  )

  const cycleSpeed = useCallback(() => {
    const next = SPEEDS[(SPEEDS.indexOf(playbackRate) + 1) % SPEEDS.length] ?? 1
    const audio = audioRef.current
    if (audio) {
      audio.defaultPlaybackRate = next
      audio.playbackRate = next
    }
    setPlaybackRate(next)
  }, [audioRef, playbackRate])

  return { seek, skip, playbackRate, cycleSpeed }
}
