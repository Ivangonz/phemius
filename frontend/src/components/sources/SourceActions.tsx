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
import { EditSourceForm } from "./EditSourceForm"

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
  const [isEditing, setIsEditing] = useState(false)
  const deleteButton = useRef<HTMLButtonElement>(null)
  const editButton = useRef<HTMLButtonElement>(null)
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

  function handleCloseEdit() {
    setIsEditing(false)
    editButton.current?.focus()
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
      <Button
        ref={editButton}
        variant="secondary"
        aria-expanded={isEditing}
        onClick={() => setIsEditing(true)}
      >
        Edit
      </Button>
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
      {isEditing && (
        <EditSourceForm
          source={source}
          onSyncStarted={onSyncStarted}
          onClose={handleCloseEdit}
        />
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
