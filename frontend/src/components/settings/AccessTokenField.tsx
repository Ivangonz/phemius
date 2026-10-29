import { useId, useState } from "react"
import { Button } from "@/components/ui/Button"
import { useRegenerateToken, type AccessStatus } from "@/hooks/useAccess"
import { getErrorMessage } from "@/lib/api"
import { NewTokenReveal } from "./NewTokenReveal"
import { RegenerateConfirm } from "./RegenerateConfirm"

const MASKED_TOKEN = "••••••••••••••••"

type AccessTokenFieldProps = { status: AccessStatus }

function tokenHint({ has_token, is_token_from_env }: AccessStatus): string {
  if (is_token_from_env)
    return "The token is set by PHEMIUS_ACCESS_TOKEN. Change the variable and restart Phemius to replace it."
  if (has_token)
    return "Phemius keeps only a hash, so the token is shown in full once, right after it is regenerated."
  return "No token yet. Generate one before switching to network or proxy mode, or Phemius prints one in its console when it starts in those modes."
}

export function AccessTokenField({ status }: AccessTokenFieldProps) {
  const regenerate = useRegenerateToken()
  const [isConfirming, setIsConfirming] = useState(false)
  const inputId = useId()
  const hintId = useId()
  const canRegenerate = !status.is_token_from_env

  function handleRegenerateClick() {
    if (status.has_token) setIsConfirming(true)
    else regenerate.mutate()
  }

  function handleConfirm() {
    setIsConfirming(false)
    regenerate.mutate()
  }

  return (
    <div className="flex min-w-0 flex-[3_1_15rem] flex-col gap-1.5">
      <label htmlFor={inputId} className="text-secondary font-semibold">
        Access token
      </label>
      <div className="flex gap-2">
        <input
          id={inputId}
          type="text"
          readOnly
          value={status.has_token ? MASKED_TOKEN : ""}
          placeholder="No token yet"
          aria-describedby={hintId}
          className="min-h-11 min-w-0 flex-1 rounded-control border border-line-control bg-surface px-3 font-mono"
        />
        {canRegenerate && (
          <Button
            variant="secondary"
            onClick={handleRegenerateClick}
            disabled={regenerate.isPending || isConfirming}
          >
            {status.has_token ? "Regenerate" : "Generate"}
          </Button>
        )}
      </div>
      <p id={hintId} className="text-small text-muted">
        {tokenHint(status)}
      </p>
      {isConfirming && (
        <RegenerateConfirm
          onConfirm={handleConfirm}
          onCancel={() => setIsConfirming(false)}
        />
      )}
      {regenerate.isError && (
        <p role="alert" className="text-secondary text-danger-ink">
          Could not regenerate the token: {getErrorMessage(regenerate.error)}
        </p>
      )}
      {regenerate.data && <NewTokenReveal token={regenerate.data} />}
    </div>
  )
}
