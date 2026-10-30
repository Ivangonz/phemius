import { useId } from "react"
import { formatVoice } from "@/lib/audioVersions"

type VoiceFieldProps = {
  voices: Record<string, string>
  value: string
  onChange: (voice: string) => void
}

export function VoiceField({ voices, value, onChange }: VoiceFieldProps) {
  const id = useId()

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className="text-secondary font-semibold tracking-[0.05em] text-muted uppercase"
      >
        Voice
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 min-w-0 rounded-control border border-line-control bg-surface px-2.5"
      >
        {Object.entries(voices).map(([voice, label]) => (
          <option key={voice} value={voice}>
            {formatVoice(voice)} · {label}
          </option>
        ))}
      </select>
    </div>
  )
}
