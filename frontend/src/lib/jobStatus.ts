import type { components } from "./api-schema"
import type { StatusKind } from "./documentStatus"

type Job = components["schemas"]["Job"]
type JobStage = components["schemas"]["JobStage"]

const STAGES: JobStage[] = ["writing_script", "narrating", "converting"]

const STAGE_LABELS: Record<JobStage, string> = {
  writing_script: "Writing script",
  narrating: "Narrating",
  converting: "Converting",
}

const STAGE_ACTIVITY: Record<JobStage, string> = {
  writing_script: "model is rewriting the document",
  narrating: "rendering the voice",
  converting: "converting the audio file",
}

const STAGE_FAILURE: Record<JobStage, string> = {
  writing_script: "Stopped while writing the script",
  narrating: "Stopped while narrating",
  converting: "Stopped while converting the audio",
}

export function describeJobStatus(job: Job): {
  label: string
  kind: StatusKind
} {
  if (job.state === "running")
    return { label: STAGE_LABELS[job.stage], kind: "working" }
  if (job.state === "failed") return { label: "Failed", kind: "failed" }
  if (job.state === "cancelled") return { label: "Cancelled", kind: "idle" }
  if (job.state === "done") return { label: "Done", kind: "ready" }
  return { label: "Waiting", kind: "idle" }
}

export function describeJobStage(job: Job, linePosition: number): string {
  const step = STAGES.indexOf(job.stage) + 1
  if (job.state === "running")
    return `Step ${step} of ${STAGES.length}: ${STAGE_ACTIVITY[job.stage]}`
  if (job.state === "failed") return STAGE_FAILURE[job.stage]
  return `Position ${linePosition} in line`
}

// The server reports progress within the current stage, so the bar spans
// all three stages to keep moving forward instead of resetting at each one.
export function overallPercent(job: Job): number {
  const stageProgress = Number.isFinite(job.progress) ? job.progress : 0
  const completed =
    STAGES.indexOf(job.stage) + Math.min(1, Math.max(0, stageProgress))
  return Math.round((completed / STAGES.length) * 100)
}

export function isActiveJob(job: Job): boolean {
  return job.state === "queued" || job.state === "running"
}
