import { useId } from "react"
import { useFormContext } from "react-hook-form"
import {
  AUDIO_FORMATS,
  type FfmpegState,
  type VoiceEngineFormValues,
} from "@/lib/voiceEngineSettings"
import { FieldShell } from "./FieldShell"
import { describedBy } from "./fieldProps"

type OutputFormatFieldProps = {
  isLocked: boolean
  ffmpeg: FfmpegState
}

const FFMPEG_NOTES: Record<FfmpegState, string | undefined> = {
  checking: "Checking for ffmpeg…",
  unknown:
    "Could not check for ffmpeg, so only WAV can be chosen. Reload the page to try again.",
  present: undefined,
  missing:
    "ffmpeg is not installed, so audio is kept as WAV. Install ffmpeg to choose M4A or MP3.",
}

export function OutputFormatField({
  isLocked,
  ffmpeg,
}: OutputFormatFieldProps) {
  const id = useId()
  const { register } = useFormContext<VoiceEngineFormValues>()
  const description = FFMPEG_NOTES[ffmpeg]

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
            disabled={format.needsFfmpeg && ffmpeg !== "present"}
          >
            {format.label}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}
