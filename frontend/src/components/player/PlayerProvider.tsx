import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type SyntheticEvent,
} from "react"
import { useAudioSource } from "@/hooks/useAudioSource"
import { useMediaSession } from "@/hooks/useMediaSession"
import { usePlaybackControls } from "@/hooks/usePlaybackControls"
import { usePlayerShortcuts } from "@/hooks/usePlayerShortcuts"
import {
  PlayerContext,
  PlayerProgressContext,
  type Player,
  type PlayerProgress,
  type Track,
} from "./playerContext"

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
  const [progress, setProgress] = useState(NO_PROGRESS)
  const source = useAudioSource(audioRef)
  const { seek, skip, playbackRate, cycleSpeed } = usePlaybackControls(audioRef)

  const startPlaying = useCallback(() => {
    // Media events drive the state, so a refused play() just stays paused.
    audioRef.current?.play().catch(() => undefined)
  }, [])

  const play = useCallback(
    (next?: Track) => {
      if (!audioRef.current) return
      if (next && next.audioId !== track?.audioId) {
        setTrack(next)
        setProgress(NO_PROGRESS)
        setHasError(false)
        source
          .load(next.audioId)
          .then((isLoaded) => isLoaded && startPlaying())
          .catch(() => setHasError(true))
        return
      }
      if (next) setTrack(next)
      if (next || track) startPlaying()
    },
    [track, source, startPlaying],
  )

  const pause = useCallback(() => audioRef.current?.pause(), [])

  const toggle = useCallback(() => {
    if (audioRef.current?.paused === false) pause()
    else play()
  }, [play, pause])

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

  function handleLoadedMetadata(event: SyntheticEvent<HTMLAudioElement>) {
    source.markLoaded()
    handleProgress(event)
  }

  function handleError(event: SyntheticEvent<HTMLAudioElement>) {
    const shouldResume = !event.currentTarget.paused
    void source.recover().then((isRecovered) => {
      if (isRecovered && shouldResume) startPlaying()
      if (isRecovered) return
      setHasError(true)
      setIsPlaying(false)
    })
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
          onLoadedMetadata={handleLoadedMetadata}
          onError={handleError}
        />
      </PlayerProgressContext>
    </PlayerContext>
  )
}
