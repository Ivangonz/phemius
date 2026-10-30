import type { Job } from "@/hooks/useQueue"
import { describeJobStage, overallPercent } from "@/lib/jobStatus"
import { ElapsedTime } from "./ElapsedTime"

const BAR_CLASSES: Record<Job["state"], string> = {
  running: "bg-primary",
  failed: "bg-danger-ink",
  queued: "bg-line-dashed",
  done: "bg-primary",
  cancelled: "bg-line-dashed",
}

type JobProgressProps = {
  job: Job
  title: string
  linePosition: number
}

export function JobProgress({ job, title, linePosition }: JobProgressProps) {
  const percent = overallPercent(job)

  return (
    <div>
      <div className="mb-1.5 flex justify-between gap-3 text-secondary text-muted">
        <span>{describeJobStage(job, linePosition)}</span>
        <ElapsedTime
          started={job.started}
          finished={job.finished}
          isTicking={job.state === "running"}
        />
      </div>
      <div
        role="progressbar"
        aria-label={`${title} progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={`${percent}%`}
        className="h-2 overflow-hidden rounded-pill bg-line"
      >
        <div
          className={`h-2 rounded-pill transition-[width] ${BAR_CLASSES[job.state]}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
