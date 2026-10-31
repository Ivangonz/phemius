import { useId, type ReactNode } from "react"
import { useFormContext, type FieldValues, type Path } from "react-hook-form"
import { FieldShell } from "./FieldShell"
import { describedBy, INPUT_CLASSES } from "./fieldProps"

type TextSettingFieldProps<T extends FieldValues> = {
  name: NoInfer<Path<T>>
  label: string
  isLocked: boolean
  isNumber?: boolean
  description?: ReactNode
  placeholder?: string
}

// T defaults to never so a caller must name its form type and tsc checks
// `name` against it.
export function TextSettingField<T extends FieldValues = never>({
  name,
  label,
  isLocked,
  isNumber = false,
  description,
  placeholder,
}: TextSettingFieldProps<T>) {
  const id = useId()
  const { register, formState, getFieldState } = useFormContext<T>()
  const error = getFieldState(name, formState).error?.message

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
        type={isNumber ? "number" : "text"}
        inputMode={isNumber ? "numeric" : undefined}
        spellCheck={false}
        autoComplete="off"
        placeholder={placeholder}
        disabled={isLocked}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, { isLocked, description, error })}
        className={`${INPUT_CLASSES} ${isNumber ? "max-w-40" : ""}`}
        {...register(name, isNumber ? { valueAsNumber: true } : undefined)}
      />
    </FieldShell>
  )
}
