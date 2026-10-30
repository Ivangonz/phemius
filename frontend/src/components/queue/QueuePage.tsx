import { PageHeader } from "@/components/PageHeader"
import { ListError } from "@/components/library/ListError"
import { useQueue, type Job } from "@/hooks/useQueue"
import { EmptyQueue } from "./EmptyQueue"
import { JobList } from "./JobList"
import { PauseQueueButton } from "./PauseQueueButton"

const VOICE_ORDER_NOTE =
  "Voices render one at a time, so waiting jobs start in order."

function countState(jobs: Job[], state: Job["state"]): number {
  return jobs.filter((job) => job.state === state).length
}

function describeQueue(jobs: Job[] | undefined, isPaused: boolean): string {
  if (!jobs) return "Loading the queue…"
  const counts = [
    `${countState(jobs, "running")} running`,
    `${countState(jobs, "queued")} waiting`,
    `${countState(jobs, "failed")} failed`,
  ].join(" · ")
  const note = isPaused
    ? "The queue is paused. Running steps finish, and nothing new starts until you resume it."
    : VOICE_ORDER_NOTE
  return `${counts}. ${note}`
}

export function QueuePage() {
  const result = useQueue()
  const page = result.data
  const isPaused = page?.is_paused ?? false

  return (
    <div className="flex flex-col gap-5.5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader
          title="Queue and activity"
          description={describeQueue(page?.items, isPaused)}
        />
        {page && <PauseQueueButton isPaused={isPaused} />}
      </div>
      {result.isError && !page && (
        <ListError
          title="The queue could not be loaded."
          error={result.error}
          onRetry={() => result.refetch()}
        />
      )}
      {page?.items.length === 0 && <EmptyQueue />}
      {page && page.items.length > 0 && <JobList jobs={page.items} />}
    </div>
  )
}
