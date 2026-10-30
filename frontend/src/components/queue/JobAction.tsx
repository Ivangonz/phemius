import { Button } from "@/components/ui/Button"
import { useCancelJob, useRetryJob, type Job } from "@/hooks/useQueue"
import { getErrorMessage } from "@/lib/api"
import { isActiveJob } from "@/lib/jobStatus"

type JobActionProps = {
  job: Job
  title: string
}

export function JobAction({ job, title }: JobActionProps) {
  const cancel = useCancelJob()
  const retry = useRetryJob()
  const isCancel = isActiveJob(job)
  const action = isCancel ? cancel : retry
  const label = isCancel ? "Cancel" : "Retry"

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        aria-label={`${label} ${title}`}
        disabled={action.isPending}
        onClick={() => action.mutate(job.id)}
      >
        {label}
      </Button>
      {action.isError && (
        <p role="alert" className="text-small text-danger-ink">
          {getErrorMessage(action.error)}
        </p>
      )}
    </div>
  )
}
