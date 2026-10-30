import { Button } from "@/components/ui/Button"
import { useSourceAction, type SourceView } from "@/hooks/useSources"
import { getErrorMessage } from "@/lib/api"

type SourceActionsProps = { source: SourceView }

export function SourceActions({ source }: SourceActionsProps) {
  const action = useSourceAction()
  const isPaused = source.status === "paused"

  function handleToggle() {
    action.mutate({ id: source.id, action: isPaused ? "resume" : "pause" })
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        disabled={action.isPending}
        onClick={handleToggle}
      >
        {isPaused ? "Resume" : "Pause"}
      </Button>
      {action.error && (
        <p role="alert" className="w-full text-secondary text-danger-ink">
          Error: {getErrorMessage(action.error)}
        </p>
      )}
    </div>
  )
}
