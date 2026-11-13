import { useEffect, useId } from "react"
import { Button } from "@/components/ui/Button"
import { useDefaultVoice } from "@/hooks/useDefaultVoice"
import { useVoiceInstalls } from "@/hooks/useVoiceInstalls"
import { useVoicePreview } from "@/hooks/useVoicePreview"
import { useVoices, type VoiceView } from "@/hooks/useVoices"
import { getErrorMessage } from "@/lib/api"
import { VoiceInstall } from "./VoiceInstall"
import { VoiceListStatus } from "./VoiceListStatus"
import { VoiceOption } from "./VoiceOption"
import { VoicePreviewButton } from "./VoicePreviewButton"

type VoiceListProps = { engineLabel: string; isLocked: boolean }

const LOCKED_NOTE =
  "Locked: the default voice is set by PHEMIUS_VOICE on the server. Unset it and restart to choose here."
// Stable, so the install tracking sees no change while the list loads.
const NO_VOICES: VoiceView[] = []

export function VoiceList({ engineLabel, isLocked }: VoiceListProps) {
  const name = useId()
  const voices = useVoices()
  const items = voices.data?.items ?? NO_VOICES
  const savedDefault = items.find((voice) => voice.is_default)?.id
  const defaultVoice = useDefaultVoice(savedDefault)
  const installs = useVoiceInstalls(items)
  const { preview, toggle, stop } = useVoicePreview()
  const previewVoiceId = preview?.voiceId
  const isPreviewListed = items.some((voice) => voice.id === previewVoiceId)

  // A saved engine change swaps the list; a sample of a voice that left it stops.
  useEffect(() => {
    if (previewVoiceId && !isPreviewListed) stop()
  }, [previewVoiceId, isPreviewListed, stop])

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

  const activePreviewId =
    preview && preview.status !== "failed" ? preview.voiceId : null
  const labelOf = (voiceId: string) =>
    items.find((voice) => voice.id === voiceId)?.label ?? voiceId
  const waitsFor = (voiceId: string) =>
    installs.busyId && installs.busyId !== voiceId
      ? labelOf(installs.busyId)
      : null

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
                  isStarting={installs.isStarting(voice.id)}
                  startError={installs.startError(voice.id)}
                  waitsFor={waitsFor(voice.id)}
                  onInstall={() => installs.install(voice.id)}
                />
              }
            />
          ))}
        </ul>
      )}
      <VoiceListStatus
        saveError={defaultVoice.error}
        isRefreshFailed={voices.isRefetchError}
        preview={preview}
        installNote={installs.note}
        labelOf={labelOf}
      />
    </fieldset>
  )
}
