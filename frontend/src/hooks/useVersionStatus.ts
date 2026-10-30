import type { AudioVersion } from "@/lib/audioVersions"
import { describeJob, isJobActive } from "@/lib/documentStatus"
import { useAudioJob } from "./useAudioJob"

export function useVersionStatus(version: AudioVersion) {
  const job = useAudioJob(version.id, isJobActive(version))
  if (!job) return describeJob(version)

  const status = describeJob({ status: job.state, stage: job.stage })
  if (job.state !== "running") return status
  return {
    ...status,
    label: `${status.label} ${Math.round(job.progress * 100)}%`,
  }
}
