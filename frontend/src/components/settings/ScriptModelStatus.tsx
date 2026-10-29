import type { ScriptModelConnection } from "@/hooks/useScriptModels"
import { ApiError, getErrorMessage } from "@/lib/api"
import { ConnectionResult } from "./ConnectionResult"

type ScriptModelStatusProps = {
  saveError: Error | null
  isSaved: boolean
  hasNoChanges: boolean
  isTesting: boolean
  connection: ScriptModelConnection | undefined
}

// One live region for the outcome of Save and Test connection.
export function ScriptModelStatus({
  saveError,
  isSaved,
  hasNoChanges,
  isTesting,
  connection,
}: ScriptModelStatusProps) {
  const hint = saveError instanceof ApiError ? saveError.hint : undefined

  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-1">
      {saveError && (
        <div className="flex flex-col gap-0.5 text-secondary">
          <p className="font-semibold text-danger-ink">
            Not saved: {getErrorMessage(saveError)}
          </p>
          {hint && <p>{hint}</p>}
        </div>
      )}
      {isSaved && <p className="text-secondary">Saved.</p>}
      {hasNoChanges && !isSaved && !saveError && (
        <p className="text-secondary text-muted">No changes to save.</p>
      )}
      {isTesting && (
        <p className="text-secondary text-muted">Testing the connection…</p>
      )}
      {connection && <ConnectionResult result={connection} />}
    </div>
  )
}
