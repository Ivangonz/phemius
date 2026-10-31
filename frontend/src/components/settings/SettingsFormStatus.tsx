import type { ReactNode } from "react"
import { ApiError, getErrorMessage } from "@/lib/api"

type SettingsFormStatusProps = {
  saveError: Error | null
  isSaved: boolean
  hasNoChanges: boolean
  isTesting: boolean
  testResult: ReactNode
}

// One live region for the outcome of Save and Test.
export function SettingsFormStatus({
  saveError,
  isSaved,
  hasNoChanges,
  isTesting,
  testResult,
}: SettingsFormStatusProps) {
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
      {testResult}
    </div>
  )
}
