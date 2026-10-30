import type { Job } from "@/hooks/useQueue"
import { JobCard } from "./JobCard"

// Waiting jobs start oldest first, while the list shows newest first.
function linePositions(jobs: Job[]): Map<number, number> {
  const waiting = jobs
    .filter((job) => job.state === "queued")
    .sort((a, b) => a.created - b.created || a.id - b.id)
  return new Map(waiting.map((job, index) => [job.id, index + 1]))
}

export function JobList({ jobs }: { jobs: Job[] }) {
  const positions = linePositions(jobs)

  return (
    <ul aria-label="Jobs" className="flex flex-col gap-3">
      {jobs.map((job) => (
        <li key={job.id}>
          <JobCard job={job} linePosition={positions.get(job.id) ?? 0} />
        </li>
      ))}
    </ul>
  )
}
