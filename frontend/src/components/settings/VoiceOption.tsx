import type { ReactNode } from "react"
import type { VoiceView } from "@/hooks/useVoices"
import { voiceStateText } from "@/lib/voiceList"

type VoiceOptionProps = {
  voice: VoiceView
  name: string
  isChecked: boolean
  isDisabled: boolean
  onSelect: (voiceId: string) => void
  action: ReactNode
  footer: ReactNode
}

export function VoiceOption({
  voice,
  name,
  isChecked,
  isDisabled,
  onSelect,
  action,
  footer,
}: VoiceOptionProps) {
  const details = [voice.accent, voiceStateText(voice, isChecked)]
    .filter(Boolean)
    .join(" · ")

  return (
    <li className="flex min-w-0 flex-[1_1_15rem] flex-col gap-2 rounded-control border border-line bg-surface p-2.5 has-checked:border-primary has-checked:bg-selected">
      <div className="flex items-center gap-2.5">
        <label className="flex min-h-11 min-w-0 flex-1 cursor-pointer items-center gap-2.5 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary has-disabled:cursor-not-allowed">
          <input
            type="radio"
            name={name}
            value={voice.id}
            checked={isChecked}
            disabled={isDisabled}
            onChange={() => onSelect(voice.id)}
            className="size-4.5 flex-none accent-primary"
          />
          <span className="flex min-w-0 flex-col">
            <span className="font-semibold">{voice.label}</span>
            <span className="text-secondary text-muted">{details}</span>
            {voice.license && (
              <span className="text-label text-muted">
                Licence: {voice.license}
              </span>
            )}
          </span>
        </label>
        {action}
      </div>
      {footer}
    </li>
  )
}
