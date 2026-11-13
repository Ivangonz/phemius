import { useCallback, useEffect, useRef, useState } from "react"
import { api, getErrorMessage } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { voicePath } from "./useVoices"

type VoicePreview = components["schemas"]["VoicePreview"]

export type PreviewState =
  | { voiceId: string; status: "loading" | "playing" }
  | { voiceId: string; status: "failed"; message: string }
  | null

// Its own audio element, separate from the player bar's, so a preview never
// replaces or pauses what the player holds. One element means one sample.
export function useVoicePreview() {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const requestRef = useRef(0)
  const [preview, setPreview] = useState<PreviewState>(null)

  const stop = useCallback(() => {
    requestRef.current += 1
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      audio.removeAttribute("src")
    }
    setPreview(null)
  }, [])

  useEffect(() => stop, [stop])

  const audioElement = useCallback(() => {
    if (!audioRef.current) {
      const audio = new Audio()
      audio.addEventListener("ended", () => setPreview(null))
      audioRef.current = audio
    }
    return audioRef.current
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
        await audio.play()
        if (isCurrent()) setPreview({ voiceId, status: "playing" })
      } catch (error) {
        if (!isCurrent()) return
        setPreview({
          voiceId,
          status: "failed",
          message: getErrorMessage(error),
        })
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

  return { preview, toggle }
}
