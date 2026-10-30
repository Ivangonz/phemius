import { useUpdateSource, type SourceView } from "@/hooks/useSources"
import {
  toSourceChange,
  toSourceFormValues,
  type SourceFormValues,
} from "@/lib/sourceForm"
import { SourceForm } from "./SourceForm"

type EditSourceFormProps = {
  source: SourceView
  onSyncStarted: (source: SourceView) => void
  onClose: () => void
}

export function EditSourceForm({
  source,
  onSyncStarted,
  onClose,
}: EditSourceFormProps) {
  const update = useUpdateSource()

  async function handleSave(values: SourceFormValues) {
    const change = toSourceChange(values, source)
    if (Object.keys(change).length > 0)
      await update.mutateAsync({ id: source.id, change })
    // A new path restarts the watcher and syncs the folder.
    if (change.config) onSyncStarted(source)
    onClose()
  }

  return (
    <SourceForm
      label={`Edit ${source.name}`}
      defaultValues={toSourceFormValues(source)}
      isPathLocked={source.is_locked}
      submitLabel="Save"
      onSave={handleSave}
      onCancel={onClose}
    />
  )
}
