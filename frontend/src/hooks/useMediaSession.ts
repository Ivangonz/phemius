import { useEffect } from "react"
import {
  SKIP_BACK_SECONDS,
  SKIP_FORWARD_SECONDS,
  type Player,
} from "@/components/player/playerContext"

function hasMediaSession(): boolean {
  return typeof navigator !== "undefined" && "mediaSession" in navigator
}

function setActionHandler(
  action: MediaSessionAction,
  handler: MediaSessionActionHandler | null,
): void {
  try {
    navigator.mediaSession.setActionHandler(action, handler)
  } catch {
    // Browsers throw for actions they do not support; the rest still work.
  }
}

export function useMediaSession({
  track,
  isPlaying,
  play,
  pause,
  seek,
  skip,
}: Player): void {
  useEffect(() => {
    if (!hasMediaSession()) return
    const canDescribe = track && typeof MediaMetadata !== "undefined"
    navigator.mediaSession.metadata = canDescribe
      ? new MediaMetadata({
          title: track.title,
          artist: track.meta,
          album: "Phemius",
        })
      : null
  }, [track])

  useEffect(() => {
    if (!hasMediaSession()) return
    const state = isPlaying ? "playing" : "paused"
    navigator.mediaSession.playbackState = track ? state : "none"
  }, [track, isPlaying])

  useEffect(() => {
    if (!hasMediaSession()) return
    const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
      ["play", () => play()],
      ["pause", pause],
      ["seekbackward", (d) => skip(-(d.seekOffset ?? SKIP_BACK_SECONDS))],
      ["seekforward", (d) => skip(d.seekOffset ?? SKIP_FORWARD_SECONDS)],
      ["seekto", (d) => seek(d.seekTime ?? NaN)],
    ]
    handlers.forEach(([action, handler]) => setActionHandler(action, handler))
    return () => handlers.forEach(([action]) => setActionHandler(action, null))
  }, [play, pause, seek, skip])
}
