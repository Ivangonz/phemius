import type { ScriptModelConnection } from "@/hooks/useScriptModels"

type ConnectionResultProps = { result: ScriptModelConnection }

// Says OK or Failed in words, so the color is never the only signal.
export function ConnectionResult({ result }: ConnectionResultProps) {
  if (!result.is_reachable) {
    return (
      <div className="flex flex-col gap-0.5 text-secondary">
        <p className="font-semibold text-danger-ink">
          Connection failed: {result.error}
        </p>
        {result.hint && <p className="text-ink">{result.hint}</p>}
      </div>
    )
  }
  if (result.provider === "offline")
    return (
      <p className="text-secondary text-success-ink">
        OK: offline rules need no connection.
      </p>
    )
  const latency =
    result.latency_ms === null || result.latency_ms === undefined
      ? ""
      : ` · ${Math.round(result.latency_ms)} ms`
  return (
    <p className="text-secondary text-success-ink">
      OK: {result.model} answered{latency}.
    </p>
  )
}
