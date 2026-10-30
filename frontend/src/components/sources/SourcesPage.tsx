import { useRef, useState } from "react"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/Button"
import type { SourceView } from "@/hooks/useSources"
import { useSyncTracker } from "@/hooks/useSyncTracker"
import { AddFolderForm } from "./AddFolderForm"
import { AddSourceTiles } from "./AddSourceTiles"
import { SourceList } from "./SourceList"

const DESCRIPTION =
  "Where documents come from. New and changed files are imported and narrated automatically."

export function SourcesPage() {
  const syncs = useSyncTracker()
  const [isAdding, setIsAdding] = useState(false)
  const addButton = useRef<HTMLButtonElement>(null)

  function handleCloseAdd() {
    setIsAdding(false)
    addButton.current?.focus()
  }

  function handleAdded(source: SourceView) {
    syncs.track(source)
    handleCloseAdd()
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader title="Sources" description={DESCRIPTION} />
        <Button
          ref={addButton}
          aria-expanded={isAdding}
          onClick={() => setIsAdding(true)}
        >
          Add source
        </Button>
      </div>
      <div className="flex flex-col gap-3.5">
        {isAdding && (
          <AddFolderForm onAdded={handleAdded} onCancel={handleCloseAdd} />
        )}
        <SourceList isSyncing={syncs.isSyncing} onSyncStarted={syncs.track} />
        <AddSourceTiles onAddFolder={() => setIsAdding(true)} />
      </div>
    </>
  )
}
