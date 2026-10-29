import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { FormProvider, useForm } from "react-hook-form"
import { Button } from "@/components/ui/Button"
import { useCheckScriptModel } from "@/hooks/useScriptModels"
import { useUpdateSettings } from "@/hooks/useSettings"
import {
  buildSettingsPatch,
  isLocked,
  scriptModelFormSchema,
  toFormValues,
  validateProviderFields,
  type ScriptModelFormValues,
  type SettingsOverview,
} from "@/lib/scriptModelSettings"
import { ProviderCards } from "./ProviderCards"
import { ProviderFields } from "./ProviderFields"
import { ScriptModelStatus } from "./ScriptModelStatus"
import { TextSettingField } from "./TextSettingField"

type ScriptModelFormProps = { overview: SettingsOverview }

const LENGTH_NOTE =
  "Higher limits allow longer scripts but use more provider credit per document. If you see credit errors, lower it."

export function ScriptModelForm({ overview }: ScriptModelFormProps) {
  const form = useForm<ScriptModelFormValues>({
    resolver: zodResolver(scriptModelFormSchema),
    defaultValues: toFormValues(overview),
  })
  const update = useUpdateSettings()
  const check = useCheckScriptModel()
  const [savedCount, setSavedCount] = useState(0)
  const [hasNoChanges, setHasNoChanges] = useState(false)

  // Resolves true when the form is valid and the server has its values.
  async function save(values: ScriptModelFormValues): Promise<boolean> {
    const errors = validateProviderFields(values, overview)
    for (const [field, message] of Object.entries(errors))
      form.setError(field as keyof ScriptModelFormValues, { message })
    if (Object.keys(errors).length > 0) return false
    const patch = buildSettingsPatch(values, overview)
    if (Object.keys(patch).length === 0) return true
    const saved = await update.mutateAsync(patch)
    form.reset(toFormValues(saved))
    setSavedCount((count) => count + 1)
    return true
  }

  function startAction() {
    check.reset()
    update.reset()
    setHasNoChanges(false)
  }

  const handleSave = form.handleSubmit(async (values) => {
    startAction()
    setHasNoChanges(
      Object.keys(buildSettingsPatch(values, overview)).length === 0,
    )
    await save(values).catch(() => false)
  })

  const handleTest = form.handleSubmit(async (values) => {
    startAction()
    if (await save(values).catch(() => false)) check.mutate()
  })

  return (
    <FormProvider {...form}>
      <form
        noValidate
        onSubmit={(event) => void handleSave(event)}
        className="flex flex-col gap-4.5"
      >
        <ProviderCards isLocked={isLocked(overview, "script_provider")} />
        <ProviderFields key={savedCount} overview={overview} />
        <TextSettingField
          name="script_max_tokens"
          label="Longest script, in tokens"
          isLocked={isLocked(overview, "script_max_tokens")}
          description={LENGTH_NOTE}
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
          <Button
            variant="secondary"
            disabled={update.isPending || check.isPending}
            onClick={() => void handleTest()}
          >
            {check.isPending ? "Testing…" : "Test connection"}
          </Button>
        </div>
        <ScriptModelStatus
          saveError={update.error}
          isSaved={update.isSuccess}
          hasNoChanges={hasNoChanges}
          isTesting={check.isPending}
          connection={check.data}
        />
      </form>
    </FormProvider>
  )
}
