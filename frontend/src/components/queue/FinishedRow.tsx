import { memo, useId } from "react"
import { RowPlayButton } from "@/components/library/RowPlayButton"
import type { Job } from "@/hooks/useQueue"
import { formatCost } from "@/lib/formatCost"
import { formatTime } from "@/lib/formatTime"

export const FinishedRow = memo(function FinishedRow({ job }: { job: Job }) {
  const titleId = useId()
  const title = job.title ?? "Untitled document"
  const details = [job.tone, job.voice].filter(Boolean).join(" · ")
  const length =
    job.duration_seconds !== null
      ? `${formatTime(job.duration_seconds)} of audio`
      : null

  return (
    <article
      aria-labelledby={titleId}
      className="flex flex-wrap items-center gap-x-5 gap-y-1.5 px-5 py-3.5"
    >
      <div className="min-w-0 flex-[1_1_260px]">
        <h3 id={titleId} className="font-medium">
          {title}
        </h3>
        {details && (
          <p className="mt-0.5 font-mono text-small text-muted">{details}</p>
        )}
      </div>
      {length && <span className="text-secondary text-muted">{length}</span>}
      {job.cost_usd !== null && (
        <span className="font-mono text-small text-muted">
          <span className="sr-only">Estimated cost </span>
          {formatCost(job.cost_usd)}
        </span>
      )}
      {job.audio_id !== null && (
        <RowPlayButton
          track={{ audioId: job.audio_id, title, meta: details }}
        />
      )}
    </article>
  )
})
