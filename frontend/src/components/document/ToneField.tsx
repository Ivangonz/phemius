import { useId } from "react"
import { formatTone } from "@/lib/audioVersions"

type ToneFieldProps = {
  tones: Record<string, string>
  suggested: string
  value: string
  onChange: (tone: string) => void
}

const CHECKED_CLASSES = "border-primary bg-selected"
const UNCHECKED_CLASSES = "border-line bg-surface hover:bg-surface-subtle"

export function ToneField({
  tones,
  suggested,
  value,
  onChange,
}: ToneFieldProps) {
  const name = useId()

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-secondary font-semibold tracking-[0.05em] text-muted uppercase">
        Tone
      </legend>
      {Object.entries(tones).map(([tone, description]) => (
        <label
          key={tone}
          className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-control border px-3 py-2.5 ${tone === value ? CHECKED_CLASSES : UNCHECKED_CLASSES}`}
        >
          <input
            type="radio"
            name={name}
            value={tone}
            checked={tone === value}
            onChange={() => onChange(tone)}
            className="mt-0.5 size-4.5 shrink-0 accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span className="font-semibold">
              {formatTone(tone)}
              {tone === suggested && " (suggested)"}
            </span>
            <span className="text-secondary text-muted">{description}</span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}
