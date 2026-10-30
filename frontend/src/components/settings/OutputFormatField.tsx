import { useId } from "react"
import { useFormContext } from "react-hook-form"
import {
  AUDIO_FORMATS,
  type VoiceEngineFormValues,
} from "@/lib/voiceEngineSettings"
import { FieldShell } from "./FieldShell"
import { describedBy } from "./fieldProps"

type OutputFormatFieldProps = {
  isLocked: boolean
  hasFfmpeg: boolean | undefined
}

const NO_FFMPEG_NOTE =
  "ffmpeg is not installed, so audio is kept as WAV. Install ffmpeg to choose M4A or MP3."

export function OutputFormatField({
  isLocked,
  hasFfmpeg,
}: OutputFormatFieldProps) {
  const id = useId()
  const { register } = useFormContext<VoiceEngineFormValues>()
  const description = hasFfmpeg === false ? NO_FFMPEG_NOTE : undefined

  return (
    <FieldShell
      id={id}
      label="Audio format"
      description={description}
      isLocked={isLocked}
    >
      <select
        id={id}
        disabled={isLocked}
        aria-describedby={describedBy(id, { isLocked, description })}
        className="min-h-11 min-w-0 flex-[1_1_14rem] cursor-pointer rounded-control border border-line-control bg-surface px-3 disabled:cursor-not-allowed disabled:bg-page disabled:text-muted"
        {...register("output_format")}
      >
        {AUDIO_FORMATS.map((format) => (
          <option
            key={format.id}
            value={format.id}
            disabled={format.needsFfmpeg && hasFfmpeg !== true}
          >
            {format.label}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}
