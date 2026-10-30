import { useEffect, useState, type KeyboardEvent } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { FormProvider, useForm, type UseFormReturn } from "react-hook-form"
import { Button } from "@/components/ui/Button"
import { ApiError } from "@/lib/api"
import { sourceFormSchema, type SourceFormValues } from "@/lib/sourceForm"
import { SaveError } from "./SaveError"
import { SourceField } from "./SourceField"

type SourceFormProps = {
  label: string
  defaultValues: SourceFormValues
  submitLabel: string
  onSave: (values: SourceFormValues) => Promise<unknown>
  onCancel: () => void
}

function showFieldErrors(
  form: UseFormReturn<SourceFormValues>,
  error: unknown,
) {
  if (!(error instanceof ApiError)) return
  for (const { field, message } of error.errors) {
    if (field.startsWith("config")) form.setError("path", { message })
    if (field === "name") form.setError("name", { message })
  }
}

export function SourceForm({
  label,
  defaultValues,
  submitLabel,
  onSave,
  onCancel,
}: SourceFormProps) {
  const form = useForm<SourceFormValues>({
    resolver: zodResolver(sourceFormSchema),
    defaultValues,
  })
  const [saveError, setSaveError] = useState<unknown>(null)
  const { isSubmitting } = form.formState

  useEffect(() => {
    form.setFocus("path")
  }, [form])

  const handleSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    await onSave(values).catch((error: unknown) => {
      setSaveError(error)
      showFieldErrors(form, error)
    })
  })

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") onCancel()
  }

  return (
    <FormProvider {...form}>
      <form
        noValidate
        aria-label={label}
        onSubmit={(event) => void handleSubmit(event)}
        onKeyDown={handleKeyDown}
        className="flex w-full flex-col gap-4 rounded-control border border-line bg-surface-subtle p-4"
      >
        <SourceField
          name="path"
          label="Folder path"
          placeholder="/home/me/docs"
        />
        <SourceField
          name="name"
          label="Name"
          description="Optional. Defaults to the folder's name."
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : submitLabel}
          </Button>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        {saveError !== null && <SaveError error={saveError} />}
      </form>
    </FormProvider>
  )
}
