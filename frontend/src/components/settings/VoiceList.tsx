import { useId } from "react"
import { Button } from "@/components/ui/Button"
import { useDefaultVoice } from "@/hooks/useDefaultVoice"
import { useVoices } from "@/hooks/useVoices"
import { getErrorMessage } from "@/lib/api"
import { VoiceOption } from "./VoiceOption"

type VoiceListProps = { engineLabel: string; isLocked: boolean }

const LOCKED_NOTE =
  "Locked: the default voice is set by PHEMIUS_VOICE on the server. Unset it and restart to choose here."

export function VoiceList({ engineLabel, isLocked }: VoiceListProps) {
  const name = useId()
  const voices = useVoices()
  const items = voices.data?.items ?? []
  const savedDefault = items.find((voice) => voice.is_default)?.id
  const defaultVoice = useDefaultVoice(savedDefault)

  if (voices.isPending) return <p className="text-muted">Loading voices…</p>
  if (voices.isError && !voices.data) {
    return (
      <div role="alert" className="flex flex-col items-start gap-2">
        <p className="font-semibold text-danger-ink">
          Voices could not be loaded: {getErrorMessage(voices.error)}
        </p>
        <Button variant="secondary" onClick={() => void voices.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-secondary font-semibold">
        Default voice ({engineLabel})
      </legend>
      {isLocked && <p className="text-secondary text-muted">{LOCKED_NOTE}</p>}
      {items.length === 0 ? (
        <p className="text-muted">
          This engine offers no voices yet. Check its setup above, then save.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {items.map((voice) => (
            <VoiceOption
              key={voice.id}
              voice={voice}
              name={name}
              isChecked={voice.id === defaultVoice.selectedId}
              isDisabled={isLocked}
              onSelect={defaultVoice.select}
            />
          ))}
        </ul>
      )}
      <div role="status" className="flex flex-col gap-0.5 text-secondary">
        {defaultVoice.error && (
          <p className="font-semibold text-danger-ink">
            Not saved: {getErrorMessage(defaultVoice.error)}
          </p>
        )}
        {voices.isRefetchError && (
          <p className="text-muted">
            Could not refresh the voice list; showing the last one loaded.
          </p>
        )}
      </div>
    </fieldset>
  )
}
