import { ApiError, getErrorMessage } from "./api"
import type { components } from "./api-schema"
import type { StatusKind } from "./documentStatus"

type UploadResult = components["schemas"]["UploadResult"]

export type UploadOutcome = {
  label: string
  kind: StatusKind
  isFinished: boolean
  message?: string
  hint?: string
}

export const WAITING: UploadOutcome = {
  label: "Waiting",
  kind: "idle",
  isFinished: false,
}

export const UPLOADING: UploadOutcome = {
  label: "Uploading…",
  kind: "working",
  isFinished: false,
}

function finished(
  label: string,
  kind: StatusKind,
  message?: string,
): UploadOutcome {
  return { label, kind, isFinished: true, message }
}

export function describeUploadResult(result: UploadResult): UploadOutcome {
  const isStored = result.doc_id !== null && result.doc_id !== undefined
  if (result.error && !isStored)
    return finished("Failed", "failed", result.error)
  if (result.error)
    return finished("Added, audio did not start", "failed", result.error)
  if (result.duplicate) return finished("Already in your library", "idle")
  if (result.is_audio_skipped)
    return finished(
      "Added without audio",
      "ready",
      "It does not read well aloud, so no audio was queued.",
    )
  return finished("Added", "ready")
}

export function describeUploadError(error: unknown): UploadOutcome {
  const hint = error instanceof ApiError ? error.hint : undefined
  return { ...finished("Failed", "failed", getErrorMessage(error)), hint }
}
