import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type SyntheticEvent,
} from "react"
import { useMediaSession } from "@/hooks/useMediaSession"
import { usePlayerShortcuts } from "@/hooks/usePlayerShortcuts"
import { audioFileUrl } from "@/lib/api"
import {
  PlayerContext,
  PlayerProgressContext,
  type Player,
  type PlayerProgress,
  type Track,
} from "./playerContext"

const SPEEDS = [1, 1.25, 1.5, 2, 0.75]
const NO_PROGRESS: PlayerProgress = { currentTime: 0, duration: 0 }

function readProgress(audio: HTMLAudioElement): PlayerProgress {
  const duration = Number.isFinite(audio.duration) ? audio.duration : 0
  return { currentTime: audio.currentTime, duration }
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [progress, setProgress] = useState(NO_PROGRESS)

  const play = useCallback(
    (next?: Track) => {
      const audio = audioRef.current
      if (!audio) return
      if (next) {
        if (next.audioId !== track?.audioId) {
          setProgress(NO_PROGRESS)
          setHasError(false)
          audio.src = audioFileUrl(next.audioId)
        }
        setTrack(next)
      } else if (!track) {
        return
      }
      // Media events drive the state, so a refused play() just stays paused.
      audio.play().catch(() => undefined)
    },
    [track],
  )

  const pause = useCallback(() => audioRef.current?.pause(), [])

  const toggle = useCallback(() => {
    if (audioRef.current?.paused === false) pause()
    else play()
  }, [play, pause])

  const seek = useCallback((seconds: number) => {
    const audio = audioRef.current
    if (!audio || !Number.isFinite(seconds)) return
    const end = Number.isFinite(audio.duration) ? audio.duration : seconds
    audio.currentTime = Math.min(Math.max(0, seconds), end)
  }, [])

  const skip = useCallback(
    (deltaSeconds: number) => {
      const audio = audioRef.current
      if (audio) seek(audio.currentTime + deltaSeconds)
    },
    [seek],
  )

  const cycleSpeed = useCallback(() => {
    const next = SPEEDS[(SPEEDS.indexOf(playbackRate) + 1) % SPEEDS.length] ?? 1
    const audio = audioRef.current
    if (audio) {
      audio.defaultPlaybackRate = next
      audio.playbackRate = next
    }
    setPlaybackRate(next)
  }, [playbackRate])

  const player = useMemo<Player>(
    () => ({
      track,
      isPlaying,
      hasError,
      playbackRate,
      play,
      pause,
      toggle,
      seek,
      skip,
      cycleSpeed,
    }),
    [
      track,
      isPlaying,
      hasError,
      playbackRate,
      play,
      pause,
      toggle,
      seek,
      skip,
      cycleSpeed,
    ],
  )

  useMediaSession(player)
  usePlayerShortcuts(player)

  function handleProgress(event: SyntheticEvent<HTMLAudioElement>) {
    setProgress(readProgress(event.currentTarget))
  }

  function handleError() {
    setHasError(true)
    setIsPlaying(false)
  }

  return (
    <PlayerContext value={player}>
      <PlayerProgressContext value={progress}>
        {children}
        <audio
          ref={audioRef}
          preload="metadata"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          onTimeUpdate={handleProgress}
          onDurationChange={handleProgress}
          onLoadedMetadata={handleProgress}
          onError={handleError}
        />
      </PlayerProgressContext>
    </PlayerContext>
  )
}
