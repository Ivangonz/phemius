import { useId } from "react"
import { useLibraryConfig } from "@/hooks/useLibraryConfig"
import { useUpdateSettings } from "@/hooks/useSettings"
import { ApiError, getErrorMessage } from "@/lib/api"
import { formatTone } from "@/lib/audioVersions"
import { savedValue, type SettingsOverview } from "@/lib/settingsFields"
import { FieldShell } from "./FieldShell"
import { describedBy } from "./fieldProps"

type DefaultToneFieldProps = { overview: SettingsOverview; isLocked: boolean }

// The pipeline uses the document's suggested tone first, and the model or the
// offline rules nearly always suggest one, so say plainly when this applies.
const DESCRIPTION =
  "Used only when a document has no suggested tone. You can still pick a tone for each version."

function toneError(error: Error | null): string | undefined {
  if (!error) return undefined
  const fieldError =
    error instanceof ApiError
      ? error.errors.find((item) => item.field === "default_tone")
      : undefined
  return fieldError?.message ?? getErrorMessage(error)
}

export function DefaultToneField({
  overview,
  isLocked,
}: DefaultToneFieldProps) {
  const id = useId()
  const config = useLibraryConfig()
  const update = useUpdateSettings()
  const saved = savedValue(overview, "default_tone")
  const value = update.isPending
    ? (update.variables.default_tone ?? saved)
    : saved
  const tones = Object.keys(config.data?.tones ?? {})
  const options = tones.includes(saved) ? tones : [saved, ...tones]
  const error = toneError(update.error)

  return (
    <div className="flex flex-col gap-1">
      <FieldShell
        id={id}
        label="Default tone"
        description={DESCRIPTION}
        error={error}
        isLocked={isLocked}
      >
        <select
          id={id}
          value={value}
          disabled={isLocked}
          aria-describedby={describedBy(id, {
            isLocked,
            description: DESCRIPTION,
            error,
          })}
          onChange={(event) =>
            update.mutate({ default_tone: event.target.value })
          }
          className="min-h-11 min-w-0 flex-[1_1_14rem] cursor-pointer rounded-control border border-line-control bg-surface px-3 disabled:cursor-not-allowed disabled:bg-page disabled:text-muted"
        >
          {options.map((tone) => (
            <option key={tone} value={tone}>
              {formatTone(tone)}
            </option>
          ))}
        </select>
      </FieldShell>
      <p role="status" className="text-secondary">
        {update.isSuccess && "Default tone saved."}
      </p>
    </div>
  )
}
