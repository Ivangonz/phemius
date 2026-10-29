import { useId } from "react"
import { useFormContext, useWatch } from "react-hook-form"
import { Button } from "@/components/ui/Button"
import { useOllamaModels } from "@/hooks/useScriptModels"
import { formatBytes } from "@/lib/formatBytes"
import type { ScriptModelFormValues } from "@/lib/scriptModelSettings"
import { FieldShell } from "./FieldShell"
import { OllamaListStatus } from "./OllamaListStatus"
import { describedBy, INPUT_CLASSES } from "./fieldProps"

type OllamaModelFieldProps = { isLocked: boolean }

export function OllamaModelField({ isLocked }: OllamaModelFieldProps) {
  const id = useId()
  const { register, formState, control } =
    useFormContext<ScriptModelFormValues>()
  const current = useWatch({ control, name: "ollama_model" })
  const installed = useOllamaModels(true)
  const models = installed.data?.models ?? []
  const isListed = models.some((model) => model.name === current)
  const error = formState.errors.ollama_model?.message
  const description = <OllamaListStatus query={installed} />

  return (
    <FieldShell
      id={id}
      label="Model"
      description={description}
      error={error}
      isLocked={isLocked}
    >
      <select
        id={id}
        disabled={isLocked}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, { isLocked, description, error })}
        className={INPUT_CLASSES}
        {...register("ollama_model")}
      >
        {current && !isListed && (
          <option value={current}>{current} (not in the list)</option>
        )}
        {models.map((model) => (
          <option key={model.name} value={model.name}>
            {model.name} ({formatBytes(model.size_bytes)})
          </option>
        ))}
      </select>
      <Button
        variant="secondary"
        disabled={installed.isFetching}
        onClick={() => void installed.refetch()}
      >
        {installed.isFetching ? "Detecting…" : "Detect installed models"}
      </Button>
    </FieldShell>
  )
}
