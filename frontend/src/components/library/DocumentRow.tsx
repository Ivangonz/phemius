import { memo, useId } from "react"
import { Link } from "@tanstack/react-router"
import type { DocumentListItem } from "@/hooks/useDocuments"
import { describeStatus } from "@/lib/documentStatus"
import { formatBytes } from "@/lib/formatBytes"
import { RowPlayButton } from "./RowPlayButton"
import { StatusBadge } from "./StatusBadge"
import { SuitabilityBadge } from "./SuitabilityBadge"

function describeLength({ format, size_bytes }: DocumentListItem) {
  if (!format || size_bytes === null) return null
  return `${format.toUpperCase()} · ${formatBytes(size_bytes)}`
}

const CHIP_CLASSES = "rounded-pill bg-chip px-2 py-0.5 text-chip-ink"

export const DocumentRow = memo(function DocumentRow({
  document,
}: {
  document: DocumentListItem
}) {
  const titleId = useId()
  const status = describeStatus(document)
  const length = describeLength(document)
  const playableAudioId = document.status === "done" ? document.audio_id : null

  return (
    <article
      aria-labelledby={titleId}
      className="flex items-center gap-3 px-4 py-3 md:gap-4 md:px-5"
    >
      {playableAudioId !== null ? (
        <RowPlayButton
          track={{
            audioId: playableAudioId,
            title: document.title,
            meta: document.category,
          }}
        />
      ) : (
        <span className="size-11 shrink-0" aria-hidden="true" />
      )}
      <div className="min-w-0 flex-1">
        <h2 id={titleId} className="truncate font-semibold">
          <Link
            to="/docs/$documentId"
            params={{ documentId: String(document.id) }}
            className="rounded-sm hover:text-primary hover:underline"
          >
            {document.title}
          </Link>
        </h2>
        <p className="truncate font-mono text-small text-muted">
          {document.source}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5 text-small">
          <span className={CHIP_CLASSES}>
            <span className="sr-only">Category: </span>
            {document.category}
          </span>
          <span className={CHIP_CLASSES}>
            <span className="sr-only">Suggested tone: </span>
            {document.suggested_tone}
          </span>
          <SuitabilityBadge suitability={document.audio_suitability} />
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <StatusBadge label={status.label} kind={status.kind} />
        {length && (
          <span className="font-mono text-small text-muted">{length}</span>
        )}
      </div>
    </article>
  )
})
