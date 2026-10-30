import { memo, useId } from "react"
import { Link } from "@tanstack/react-router"
import { StatusBadge } from "@/components/library/StatusBadge"
import type { Job } from "@/hooks/useQueue"
import { describeJobStatus } from "@/lib/jobStatus"
import { JobAction } from "./JobAction"
import { JobFailure } from "./JobFailure"
import { JobProgress } from "./JobProgress"

type JobCardProps = {
  job: Job
  linePosition: number
}

export const JobCard = memo(function JobCard({
  job,
  linePosition,
}: JobCardProps) {
  const titleId = useId()
  const title = job.title ?? "Untitled document"
  const status = describeJobStatus(job)
  const isFailed = job.state === "failed"
  const border = isFailed ? "border-danger-line" : "border-line"
  const details = [job.tone, job.voice].filter(Boolean).join(" · ")

  return (
    <article
      aria-labelledby={titleId}
      className={`flex flex-col gap-3 rounded-panel border bg-surface px-5 py-4.5 ${border}`}
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="min-w-0 flex-[1_1_280px]">
          <h2 id={titleId} className="text-base font-semibold">
            {job.document_id !== null ? (
              <Link
                to="/docs/$documentId"
                params={{ documentId: String(job.document_id) }}
                className="rounded-sm hover:text-primary hover:underline"
              >
                {title}
              </Link>
            ) : (
              title
            )}
          </h2>
          {details && (
            <p className="mt-1 font-mono text-small text-muted">{details}</p>
          )}
        </div>
        <StatusBadge label={status.label} kind={status.kind} />
        <JobAction job={job} title={title} />
      </div>
      <JobProgress job={job} title={title} linePosition={linePosition} />
      {isFailed && <JobFailure error={job.error} hint={job.hint} />}
    </article>
  )
})
