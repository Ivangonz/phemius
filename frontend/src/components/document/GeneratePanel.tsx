import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/Button"
import type { DocumentDetail } from "@/hooks/useDocument"
import { useGenerateVersion } from "@/hooks/useGenerateVersion"
import { useLibraryConfig, type LibraryConfig } from "@/hooks/useLibraryConfig"
import { ApiError, getErrorMessage } from "@/lib/api"
import { ToneField } from "./ToneField"
import { VoiceField } from "./VoiceField"

type GeneratePanelProps = {
  document: DocumentDetail
  onQueued: (audioId: number) => void
}

function defaultVoice(config: LibraryConfig | undefined): string {
  const voices = Object.keys(config?.voices ?? {})
  const configured = config?.default_voice
  return configured && voices.includes(configured)
    ? configured
    : (voices[0] ?? "")
}

export function GeneratePanel({ document, onQueued }: GeneratePanelProps) {
  const headingId = useId()
  const configQuery = useLibraryConfig()
  const config = configQuery.data
  const generate = useGenerateVersion(document.id)
  const [tone, setTone] = useState(document.suggested_tone)
  const [voice, setVoice] = useState<string | null>(null)
  const chosenVoice = voice ?? defaultVoice(config)
  const hint = generate.error instanceof ApiError ? generate.error.hint : null

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    generate.mutate(
      { tone, voice: chosenVoice || null },
      { onSuccess: ({ audio_id }) => onQueued(audio_id) },
    )
  }

  return (
    <aside
      aria-labelledby={headingId}
      className="flex min-w-0 flex-[1_1_340px] flex-col gap-4.5 rounded-panel border border-line bg-surface p-4 md:p-5.5"
    >
      <h2 id={headingId} className="text-[18px] font-semibold">
        Generate a new version
      </h2>
      <p className="rounded-control bg-primary-tint px-3.5 py-3 text-secondary text-primary-tint-ink">
        <strong className="font-semibold">
          Suggested: {document.suggested_tone}.
        </strong>{" "}
        {document.tone_rationale}
      </p>
      {config ? (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4.5">
          <ToneField
            tones={config.tones}
            suggested={document.suggested_tone}
            value={tone}
            onChange={setTone}
          />
          <VoiceField
            voices={config.voices}
            value={chosenVoice}
            onChange={setVoice}
          />
          {generate.isError && (
            <div role="alert" className="text-danger-ink">
              <p>{getErrorMessage(generate.error)}</p>
              {hint && <p className="text-muted">{hint}</p>}
            </div>
          )}
          <Button type="submit" disabled={generate.isPending}>
            {generate.isPending ? "Queuing…" : "Generate version"}
          </Button>
        </form>
      ) : (
        <p
          role={configQuery.isError ? "alert" : "status"}
          className="text-muted"
        >
          {configQuery.isError
            ? `Tones and voices could not be loaded. ${getErrorMessage(configQuery.error)}`
            : "Loading tones and voices…"}
        </p>
      )}
    </aside>
  )
}
