import { useId } from "react"
import type { UploadEntry } from "@/hooks/useUploadQueue"
import { StatusBadge } from "./StatusBadge"

export function UploadItem({ entry }: { entry: UploadEntry }) {
  const nameId = useId()
  const { label, kind, message, hint } = entry.outcome

  return (
    <li
      aria-labelledby={nameId}
      className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-4 py-2.5"
    >
      <div className="min-w-0 flex-1">
        <p id={nameId} className="truncate font-mono text-small">
          {entry.name}
        </p>
        {message && <p className="text-small">{message}</p>}
        {hint && <p className="text-small text-muted">{hint}</p>}
      </div>
      <StatusBadge label={label} kind={kind} />
    </li>
  )
}
