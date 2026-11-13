import { useId } from "react"
import { Button } from "@/components/ui/Button"
import { useUpdateSettings } from "@/hooks/useSettings"
import { useVoicePreview } from "@/hooks/useVoicePreview"
import { useDownloadVoice, useVoices } from "@/hooks/useVoices"
import { getErrorMessage } from "@/lib/api"
import { VoiceInstall } from "./VoiceInstall"
import { VoiceListStatus } from "./VoiceListStatus"
import { VoiceOption } from "./VoiceOption"
import { VoicePreviewButton } from "./VoicePreviewButton"

type VoiceListProps = { engineLabel: string; isLocked: boolean }

const LOCKED_NOTE =
  "Locked: the default voice is set by PHEMIUS_VOICE on the server. Unset it and restart to choose here."

export function VoiceList({ engineLabel, isLocked }: VoiceListProps) {
  const name = useId()
  const voices = useVoices()
  const update = useUpdateSettings()
  const download = useDownloadVoice()
  const { preview, toggle } = useVoicePreview()

  if (voices.isPending) return <p className="text-muted">Loading voices…</p>
  if (voices.isError) {
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

  const items = voices.data.items
  const savedDefault = items.find((voice) => voice.is_default)?.id
  const selectedId = update.isPending
    ? update.variables.default_voice
    : savedDefault
  const activePreviewId =
    preview && preview.status !== "failed" ? preview.voiceId : null
  const isStartingFor = (voiceId: string) =>
    download.isPending && download.variables === voiceId
  const startErrorFor = (voiceId: string) =>
    download.variables === voiceId ? download.error : null
  const labelOf = (voiceId: string) =>
    items.find((voice) => voice.id === voiceId)?.label ?? voiceId

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
              isChecked={voice.id === selectedId}
              isDisabled={isLocked}
              onSelect={(voiceId) => update.mutate({ default_voice: voiceId })}
              action={
                <VoicePreviewButton
                  label={voice.label}
                  isActive={voice.id === activePreviewId}
                  onToggle={() => toggle(voice.id)}
                />
              }
              footer={
                <VoiceInstall
                  voice={voice}
                  isStarting={isStartingFor(voice.id)}
                  startError={startErrorFor(voice.id)}
                  onInstall={() => download.mutate(voice.id)}
                />
              }
            />
          ))}
        </ul>
      )}
      <VoiceListStatus
        saveError={update.error}
        preview={preview}
        labelOf={labelOf}
      />
    </fieldset>
  )
}
