import type { VoiceEngineStatus } from "@/hooks/useVoiceEngine"

type VoiceCheckResultProps = { result: VoiceEngineStatus }

// Says OK or Test failed in words, so the color is never the only signal.
export function VoiceCheckResult({ result }: VoiceCheckResultProps) {
  if (result.is_ready)
    return (
      <p className="text-secondary text-success-ink">OK: {result.message}</p>
    )
  return (
    <div className="flex flex-col gap-0.5 text-secondary">
      <p className="font-semibold text-danger-ink">
        Test failed: {result.message}
      </p>
      {result.hint && <p className="text-ink">{result.hint}</p>}
    </div>
  )
}
