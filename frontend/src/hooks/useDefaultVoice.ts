import { useCallback, useEffect, useRef, useState } from "react"
import { useUpdateSettings } from "./useSettings"

export const DEFAULT_VOICE_SAVE_DELAY_MS = 300

// Arrow keys move a radio group's selection one step at a time; waiting a
// moment saves only where the user stops. The selection shows at once.
export function useDefaultVoice(savedId: string | undefined) {
  const update = useUpdateSettings()
  const { mutate } = update
  const [chosenId, setChosenId] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const chosenRef = useRef<string | null>(null)

  const save = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = null
    const voiceId = chosenRef.current
    chosenRef.current = null
    setChosenId(null)
    if (voiceId) mutate({ default_voice: voiceId })
  }, [mutate])

  // Leaving the page within the delay still saves the last pick.
  useEffect(() => save, [save])

  const select = useCallback(
    (voiceId: string) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      chosenRef.current = voiceId
      setChosenId(voiceId)
      timerRef.current = setTimeout(save, DEFAULT_VOICE_SAVE_DELAY_MS)
    },
    [save],
  )

  const savingId = update.isPending ? update.variables.default_voice : null
  const selectedId = chosenId ?? savingId ?? savedId
  const error = chosenId ? null : update.error

  return { selectedId, select, error }
}
