import type { ButtonHTMLAttributes } from "react"

export function PlayerControlButton(
  props: ButtonHTMLAttributes<HTMLButtonElement>,
) {
  return (
    <button
      type="button"
      className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-control border border-line-control bg-surface px-2 font-mono text-small font-medium text-ink transition-colors hover:bg-surface-subtle"
      {...props}
    />
  )
}
