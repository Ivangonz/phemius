import { useCallback, useEffect, useRef, useState } from "react"
import { api, getErrorMessage } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { voicePath } from "./useVoices"

type VoicePreview = components["schemas"]["VoicePreview"]

export type PreviewState =
  | { voiceId: string; status: "loading" | "playing" }
  | { voiceId: string; status: "failed"; message: string }
  | null

type PreviewAudio = { audio: HTMLAudioElement; listeners: AbortController }

const PLAYBACK_FAILED = "The sample could not be played."

// Its own audio element, separate from the player bar's, so a preview never
// replaces or pauses what the player holds. One element means one sample.
export function useVoicePreview() {
  const previewAudioRef = useRef<PreviewAudio | null>(null)
  const requestRef = useRef(0)
  const playingRequestRef = useRef<number | null>(null)
  const [preview, setPreview] = useState<PreviewState>(null)

  const stop = useCallback(() => {
    requestRef.current += 1
    playingRequestRef.current = null
    const audio = previewAudioRef.current?.audio
    if (audio) {
      audio.pause()
      audio.removeAttribute("src")
    }
    setPreview(null)
  }, [])

  useEffect(
    () => () => {
      stop()
      previewAudioRef.current?.listeners.abort()
      previewAudioRef.current = null
    },
    [stop],
  )

  // A pause or error from an earlier sample arrives after the next one has
  // started; only the sample that is playing now may change the state.
  const audioElement = useCallback(() => {
    if (previewAudioRef.current) return previewAudioRef.current.audio
    const audio = new Audio()
    const listeners = new AbortController()
    const isPlayingNow = () =>
      playingRequestRef.current !== null &&
      playingRequestRef.current === requestRef.current
    const handleEnd = () => {
      if (isPlayingNow() && audio.paused) setPreview(null)
    }
    const handleError = () => {
      if (!isPlayingNow()) return
      setPreview(
        (current) =>
          current && {
            voiceId: current.voiceId,
            status: "failed",
            message: PLAYBACK_FAILED,
          },
      )
    }
    const { signal } = listeners
    audio.addEventListener("ended", handleEnd, { signal })
    audio.addEventListener("pause", handleEnd, { signal })
    audio.addEventListener("error", handleError, { signal })
    previewAudioRef.current = { audio, listeners }
    return audio
  }, [])

  const start = useCallback(
    async (voiceId: string) => {
      stop()
      const request = requestRef.current
      const isCurrent = () => request === requestRef.current
      setPreview({ voiceId, status: "loading" })
      try {
        const { url } = await api.post<VoicePreview>(
          `${voicePath(voiceId)}/preview`,
        )
        if (!isCurrent()) return
        const audio = audioElement()
        audio.src = url
        playingRequestRef.current = request
        await audio.play()
        if (isCurrent()) setPreview({ voiceId, status: "playing" })
      } catch (error) {
        if (!isCurrent()) return
        playingRequestRef.current = null
        const message = getErrorMessage(error)
        setPreview({ voiceId, status: "failed", message })
      }
    },
    [stop, audioElement],
  )

  const toggle = useCallback(
    (voiceId: string) => {
      const isActive =
        preview?.voiceId === voiceId && preview.status !== "failed"
      if (isActive) stop()
      else void start(voiceId)
    },
    [preview, start, stop],
  )

  return { preview, toggle, stop }
}
