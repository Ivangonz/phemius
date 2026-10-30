import { useId } from "react"
import { useFormContext } from "react-hook-form"
import { FieldShell } from "@/components/settings/FieldShell"
import { describedBy, INPUT_CLASSES } from "@/components/settings/fieldProps"
import type { SourceFormValues } from "@/lib/sourceForm"

type SourceFieldProps = {
  name: keyof SourceFormValues
  label: string
  isLocked?: boolean
  description?: string
  placeholder?: string
}

export function SourceField({
  name,
  label,
  isLocked = false,
  description,
  placeholder,
}: SourceFieldProps) {
  const id = useId()
  const { register, formState } = useFormContext<SourceFormValues>()
  const error = formState.errors[name]?.message

  return (
    <FieldShell
      id={id}
      label={label}
      description={description}
      error={error}
      isLocked={isLocked}
    >
      <input
        id={id}
        type="text"
        spellCheck={false}
        autoComplete="off"
        placeholder={placeholder}
        readOnly={isLocked}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, { isLocked, description, error })}
        className={`${INPUT_CLASSES} read-only:bg-page read-only:text-muted`}
        {...register(name)}
      />
    </FieldShell>
  )
}
