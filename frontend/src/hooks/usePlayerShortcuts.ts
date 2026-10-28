import { useEffect } from "react"
import {
  SKIP_BACK_SECONDS,
  SKIP_FORWARD_SECONDS,
  type Player,
} from "@/components/player/playerContext"

export const SHORTCUTS = {
  toggle: "k Space",
  back: "j",
  forward: "l",
}

const TEXT_ENTRY = "input, textarea, select, [contenteditable='true']"
const ACTIVATED_BY_SPACE =
  "button, a[href], summary, [role='button'], [role='checkbox'], [role='switch']"

function isFreeKeystroke(event: KeyboardEvent): boolean {
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey)
    return false
  const target = event.target instanceof Element ? event.target : null
  if (target?.closest(TEXT_ENTRY)) return false
  return !(event.key === " " && target?.closest(ACTIVATED_BY_SPACE))
}

export function usePlayerShortcuts({ track, toggle, skip }: Player): void {
  const hasTrack = track !== null

  useEffect(() => {
    if (!hasTrack) return
    const actions: Record<string, () => void> = {
      k: toggle,
      " ": toggle,
      j: () => skip(-SKIP_BACK_SECONDS),
      l: () => skip(SKIP_FORWARD_SECONDS),
    }

    function handleKeyDown(event: KeyboardEvent) {
      const action = actions[event.key]
      if (!action || !isFreeKeystroke(event)) return
      event.preventDefault()
      action()
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [hasTrack, toggle, skip])
}
