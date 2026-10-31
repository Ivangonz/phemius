import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { FormProvider, useForm } from "react-hook-form"
import { Button } from "@/components/ui/Button"
import { useLibraryConfig } from "@/hooks/useLibraryConfig"
import { useUpdateSettings } from "@/hooks/useSettings"
import { useCheckVoiceEngine } from "@/hooks/useVoiceEngine"
import { isLocked, type SettingsOverview } from "@/lib/settingsFields"
import {
  buildVoicePatch,
  toFfmpegState,
  toVoiceFormValues,
  VOICE_ENGINES,
  voiceEngineFormSchema,
  type VoiceEngineFormValues,
} from "@/lib/voiceEngineSettings"
import { OutputFormatField } from "./OutputFormatField"
import { ProviderCards } from "./ProviderCards"
import { SettingsFormStatus } from "./SettingsFormStatus"
import { VoiceCheckResult } from "./VoiceCheckResult"
import { VoiceEngineFields } from "./VoiceEngineFields"

type VoiceEngineFormProps = { overview: SettingsOverview }

const ENGINE_LOCKED_NOTE =
  "Locked: the engine is set by PHEMIUS_TTS on the server. Unset it and restart to choose here."

export function VoiceEngineForm({ overview }: VoiceEngineFormProps) {
  const form = useForm<VoiceEngineFormValues>({
    resolver: zodResolver(voiceEngineFormSchema(overview)),
    defaultValues: toVoiceFormValues(overview),
  })
  const config = useLibraryConfig()
  const update = useUpdateSettings()
  const check = useCheckVoiceEngine()
  const [savedCount, setSavedCount] = useState(0)
  const [hasNoChanges, setHasNoChanges] = useState(false)

  async function save(values: VoiceEngineFormValues) {
    const patch = buildVoicePatch(values, overview)
    if (Object.keys(patch).length === 0) return
    const saved = await update.mutateAsync(patch)
    form.reset(toVoiceFormValues(saved))
    setSavedCount((count) => count + 1)
  }

  function startAction() {
    check.reset()
    update.reset()
    setHasNoChanges(false)
  }

  const handleSave = form.handleSubmit(async (values) => {
    startAction()
    setHasNoChanges(Object.keys(buildVoicePatch(values, overview)).length === 0)
    await save(values).catch(() => undefined)
  })

  const handleTest = form.handleSubmit(async (values) => {
    startAction()
    const isSaved = await save(values).then(
      () => true,
      () => false,
    )
    if (isSaved) check.mutate()
  })

  return (
    <FormProvider {...form}>
      <form
        noValidate
        onSubmit={(event) => void handleSave(event)}
        className="flex flex-col gap-4.5"
      >
        <ProviderCards<VoiceEngineFormValues>
          name="voice_engine"
          legend="Voice engine"
          options={VOICE_ENGINES}
          isLocked={isLocked(overview, "voice_engine")}
          lockedNote={ENGINE_LOCKED_NOTE}
        />
        <VoiceEngineFields key={savedCount} overview={overview} />
        <OutputFormatField
          isLocked={isLocked(overview, "output_format")}
          ffmpeg={toFfmpegState(config.data?.ffmpeg, config.isError)}
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
            {check.isPending ? "Testing…" : "Test voice engine"}
          </Button>
        </div>
        <SettingsFormStatus
          saveError={update.error}
          isSaved={update.isSuccess}
          hasNoChanges={hasNoChanges}
          isTesting={check.isPending}
          testResult={check.data && <VoiceCheckResult result={check.data} />}
        />
      </form>
    </FormProvider>
  )
}
