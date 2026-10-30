import { useRef, useState } from "react"
import { Button } from "@/components/ui/Button"
import {
  useDeleteSource,
  useSourceAction,
  type SourceAction,
  type SourceView,
} from "@/hooks/useSources"
import { getErrorMessage } from "@/lib/api"
import { DeleteSourceConfirm } from "./DeleteSourceConfirm"

type SourceActionsProps = {
  source: SourceView
  isSyncing: boolean
  onSyncStarted: (source: SourceView) => void
}

export function SourceActions({
  source,
  isSyncing,
  onSyncStarted,
}: SourceActionsProps) {
  const action = useSourceAction()
  const deletion = useDeleteSource()
  const [isConfirming, setIsConfirming] = useState(false)
  const deleteButton = useRef<HTMLButtonElement>(null)
  const isPaused = source.status === "paused"
  const isBusy = action.isPending || deletion.isPending
  const error = action.error ?? deletion.error

  function run(name: SourceAction) {
    deletion.reset()
    action.mutate(
      { id: source.id, action: name },
      { onSuccess: () => name !== "pause" && onSyncStarted(source) },
    )
  }

  function handleCancelDelete() {
    setIsConfirming(false)
    deleteButton.current?.focus()
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        disabled={isBusy}
        onClick={() => run(isPaused ? "resume" : "pause")}
      >
        {isPaused ? "Resume" : "Pause"}
      </Button>
      {!isPaused && (
        <Button
          variant="secondary"
          disabled={isBusy || isSyncing}
          onClick={() => run("sync")}
        >
          {isSyncing ? "Syncing…" : "Sync now"}
        </Button>
      )}
      {!source.is_locked && (
        <Button
          ref={deleteButton}
          variant="secondary"
          aria-expanded={isConfirming}
          disabled={isBusy}
          onClick={() => setIsConfirming(true)}
        >
          Delete
        </Button>
      )}
      {isConfirming && (
        <DeleteSourceConfirm
          name={source.name}
          isDeleting={deletion.isPending}
          onConfirm={() => deletion.mutate(source.id)}
          onCancel={handleCancelDelete}
        />
      )}
      {error && (
        <p role="alert" className="w-full text-secondary text-danger-ink">
          Error: {getErrorMessage(error)}
        </p>
      )}
    </div>
  )
}
