import { useEffect, useRef, type FocusEvent } from "react"

// When a control in a row goes away (Install once the voice is installed),
// the browser drops focus to the page. Put it back on the row's main control.
export function useKeepFocusInRow<Target extends HTMLElement>(
  removalTrigger: unknown,
) {
  const targetRef = useRef<Target>(null)
  const hasFocusRef = useRef(false)

  useEffect(() => {
    const active = document.activeElement
    const isFocusLost = active === null || active === document.body
    if (hasFocusRef.current && isFocusLost) targetRef.current?.focus()
  }, [removalTrigger])

  const rowProps = {
    onFocus: () => {
      hasFocusRef.current = true
    },
    onBlur: (event: FocusEvent<HTMLElement>) => {
      const next = event.relatedTarget
      if (next && !event.currentTarget.contains(next))
        hasFocusRef.current = false
    },
  }

  return { targetRef, rowProps }
}
