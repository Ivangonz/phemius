import { useId } from "react"
import type { UploadEntry } from "@/hooks/useUploadQueue"
import { Button } from "@/components/ui/Button"
import { UploadItem } from "./UploadItem"

type UploadListProps = {
  entries: UploadEntry[]
  onClearFinished: () => void
}

export function UploadList({ entries, onClearFinished }: UploadListProps) {
  const titleId = useId()
  if (entries.length === 0) return null

  const hasFinished = entries.some((entry) => entry.outcome.isFinished)

  return (
    <section
      aria-labelledby={titleId}
      className="rounded-panel border border-line bg-surface"
    >
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-1.5">
        <h2 id={titleId} className="font-semibold">
          Uploads
        </h2>
        {hasFinished && (
          <Button variant="secondary" onClick={onClearFinished}>
            Clear finished
          </Button>
        )}
      </div>
      <ul aria-live="polite" className="divide-y divide-line">
        {entries.map((entry) => (
          <UploadItem key={entry.id} entry={entry} />
        ))}
      </ul>
    </section>
  )
}
