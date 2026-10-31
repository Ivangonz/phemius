import { useId, useState } from "react"
import { useFormContext, type FieldValues, type Path } from "react-hook-form"
import { Button } from "@/components/ui/Button"
import type { components } from "@/lib/api-schema"
import { FieldShell } from "./FieldShell"
import { describedBy, INPUT_CLASSES } from "./fieldProps"

type SecretStatus = components["schemas"]["SecretStatus"]

type SecretFieldProps<T extends FieldValues> = {
  name: NoInfer<Path<T>>
  label: string
  status: SecretStatus | undefined
  isOptional?: boolean
}

const STORED_NOTE =
  "Keys are stored on this computer only and never shown again."

// A saved key is never sent to the browser: the field shows "Key saved" and
// only a newly typed key is saved. T defaults to never so a caller must name
// its form type and tsc checks `name` against it.
export function SecretField<T extends FieldValues = never>({
  name,
  label,
  status,
  isOptional = false,
}: SecretFieldProps<T>) {
  const id = useId()
  const { register, formState, getFieldState, resetField } = useFormContext<T>()
  const [isReplacing, setIsReplacing] = useState(false)
  const error = getFieldState(name, formState).error?.message
  const isLocked = status?.is_locked ?? false
  const hasKey = status?.has_key ?? false
  const isEditing = !isLocked && (!hasKey || isReplacing)
  const description = isOptional
    ? `Optional: leave empty if the server needs no key. ${STORED_NOTE}`
    : STORED_NOTE

  function handleCancel() {
    resetField(name)
    setIsReplacing(false)
  }

  return (
    <FieldShell
      id={id}
      label={label}
      description={description}
      error={error}
      isLocked={isLocked}
    >
      {isEditing ? (
        <input
          id={id}
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder={hasKey ? "New key" : "Paste your key"}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, { description, error })}
          className={INPUT_CLASSES}
          {...register(name)}
        />
      ) : (
        <output
          id={id}
          aria-describedby={describedBy(id, { isLocked, description })}
          className="flex min-h-11 flex-[1_1_14rem] items-center rounded-control border border-line bg-page px-3 font-medium"
        >
          {hasKey ? "Key saved" : "No key set"}
        </output>
      )}
      {hasKey && !isLocked && !isReplacing && (
        <Button variant="secondary" onClick={() => setIsReplacing(true)}>
          Replace
        </Button>
      )}
      {isReplacing && (
        <Button variant="secondary" onClick={handleCancel}>
          Keep saved key
        </Button>
      )}
    </FieldShell>
  )
}
