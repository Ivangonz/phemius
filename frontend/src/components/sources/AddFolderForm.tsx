import { useAddSource, type SourceView } from "@/hooks/useSources"
import {
  EMPTY_SOURCE_FORM,
  toNewSource,
  type SourceFormValues,
} from "@/lib/sourceForm"
import { SourceForm } from "./SourceForm"

type AddFolderFormProps = {
  onAdded: (source: SourceView) => void
  onCancel: () => void
}

export function AddFolderForm({ onAdded, onCancel }: AddFolderFormProps) {
  const add = useAddSource()

  async function handleSave(values: SourceFormValues) {
    onAdded(await add.mutateAsync(toNewSource(values)))
  }

  return (
    <SourceForm
      label="Add a folder"
      defaultValues={EMPTY_SOURCE_FORM}
      submitLabel="Add folder"
      onSave={handleSave}
      onCancel={onCancel}
    />
  )
}
