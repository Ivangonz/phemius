import type { ReactNode } from "react"

type FieldShellProps = {
  id: string
  label: string
  children: ReactNode
  description?: ReactNode
  error?: string
  isLocked?: boolean
}

// Label, control row and the notes under it, with each note linked to the
// control so a screen reader reads them with it.
export function FieldShell({
  id,
  label,
  children,
  description,
  error,
  isLocked = false,
}: FieldShellProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-secondary font-semibold">
        {label}
      </label>
      <div className="flex flex-wrap gap-2">{children}</div>
      {isLocked && (
        <p id={`${id}-locked`} className="text-secondary text-muted">
          Locked: set by an environment variable on the server. Unset it and
          restart to change it here.
        </p>
      )}
      {description && (
        <div id={`${id}-description`} className="text-secondary text-muted">
          {description}
        </div>
      )}
      {error && (
        <p id={`${id}-error`} className="text-secondary text-danger-ink">
          Error: {error}
        </p>
      )}
    </div>
  )
}
