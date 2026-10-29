import { useId, type ReactNode } from "react"
import { useFormContext } from "react-hook-form"
import type { ScriptModelFormValues } from "@/lib/scriptModelSettings"
import { FieldShell } from "./FieldShell"
import { describedBy, INPUT_CLASSES } from "./fieldProps"

type TextFieldName = "model" | "ollama_url" | "script_base_url"

type TextSettingFieldProps = {
  name: TextFieldName | "script_max_tokens"
  label: string
  isLocked: boolean
  description?: ReactNode
  placeholder?: string
}

export function TextSettingField({
  name,
  label,
  isLocked,
  description,
  placeholder,
}: TextSettingFieldProps) {
  const id = useId()
  const { register, formState } = useFormContext<ScriptModelFormValues>()
  const error = formState.errors[name]?.message
  const isNumber = name === "script_max_tokens"

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
