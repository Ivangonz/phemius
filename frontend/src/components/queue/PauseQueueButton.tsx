import { Button } from "@/components/ui/Button"
import { useSetQueuePaused } from "@/hooks/useQueue"
import { getErrorMessage } from "@/lib/api"

export function PauseQueueButton({ isPaused }: { isPaused: boolean }) {
  const setPaused = useSetQueuePaused()

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        disabled={setPaused.isPending}
        onClick={() => setPaused.mutate(!isPaused)}
      >
        {isPaused ? "Resume queue" : "Pause queue"}
      </Button>
      {setPaused.isError && (
        <p role="alert" className="text-small text-danger-ink">
          {getErrorMessage(setPaused.error)}
        </p>
      )}
    </div>
  )
}
