import { useCallback, useMemo, useRef, type RefObject } from "react"
import { audioFileUrl } from "@/lib/api"

type AudioSource = {
  load: (audioId: number) => Promise<boolean>
  recover: () => Promise<boolean>
  markLoaded: () => void
}

function seekWhenReady(audio: HTMLAudioElement, seconds: number): void {
  // Browsers keep a seek made before metadata loads; this covers any that drop it.
  audio.currentTime = seconds
  audio.addEventListener(
    "loadedmetadata",
    () => {
      if (audio.currentTime < seconds) audio.currentTime = seconds
    },
    { once: true },
  )
}

// Points the audio element at a signed file URL. A signed URL expires, so a
// failed load fetches a fresh one once and continues from the same position.
export function useAudioSource(
  audioRef: RefObject<HTMLAudioElement | null>,
): AudioSource {
  const audioIdRef = useRef<number | null>(null)
  const hasRetriedRef = useRef(false)

  const applyUrl = useCallback(
    async (audioId: number, startAt: number): Promise<boolean> => {
      const url = await audioFileUrl(audioId)
      const audio = audioRef.current
      // A newer track may have been chosen while the URL was fetched.
      if (!audio || audioIdRef.current !== audioId) return false
      audio.src = url
      if (startAt > 0) seekWhenReady(audio, startAt)
      return true
    },
    [audioRef],
  )

  const load = useCallback(
    (audioId: number) => {
      audioIdRef.current = audioId
      hasRetriedRef.current = false
      return applyUrl(audioId, 0)
    },
    [applyUrl],
  )

  const recover = useCallback(async () => {
    const audioId = audioIdRef.current
    const audio = audioRef.current
    if (!audio || audioId === null || hasRetriedRef.current) return false
    hasRetriedRef.current = true
    return applyUrl(audioId, audio.currentTime).catch(() => false)
  }, [applyUrl, audioRef])

  const markLoaded = useCallback(() => {
    hasRetriedRef.current = false
  }, [])

  // Stable, so the player context does not change while audio plays.
  return useMemo(
    () => ({ load, recover, markLoaded }),
    [load, recover, markLoaded],
  )
}
