import type { components } from "./api-schema"
import type { DocumentStatus } from "./librarySearch"

type DocumentListItem = components["schemas"]["DocumentListItem"]
type JobStage = components["schemas"]["JobStage"]

export type StatusKind = "ready" | "working" | "failed" | "idle"

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  done: "Ready",
  running: "In progress",
  queued: "Queued",
  failed: "Failed",
  cancelled: "Cancelled",
  no_audio: "No audio",
}

const STAGE_LABELS: Record<JobStage, string> = {
  writing_script: "Writing script",
  narrating: "Narrating",
  converting: "Converting",
}

const STATUS_KINDS: Record<DocumentStatus, StatusKind> = {
  done: "ready",
  running: "working",
  queued: "working",
  failed: "failed",
  cancelled: "idle",
  no_audio: "idle",
}

export function describeStatus({
  status,
  stage,
  is_changed,
}: DocumentListItem): { label: string; kind: StatusKind } {
  const kind = STATUS_KINDS[status]
  if (status === "running" && stage) return { label: STAGE_LABELS[stage], kind }
  if (status === "no_audio" && is_changed)
    return { label: "Changed, no audio yet", kind }
  return { label: STATUS_LABELS[status], kind }
}
