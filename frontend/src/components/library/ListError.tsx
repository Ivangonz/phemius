import { Button } from "@/components/ui/Button"
import { ApiError, getErrorMessage } from "@/lib/api"

type ListErrorProps = {
  error: unknown
  onRetry: () => void
}

export function ListError({ error, onRetry }: ListErrorProps) {
  const hint = error instanceof ApiError ? error.hint : undefined

  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 rounded-panel border border-danger-line bg-surface p-5"
    >
      <p className="font-semibold text-danger-ink">
        The library could not be loaded.
      </p>
      <p>{getErrorMessage(error)}</p>
      {hint && <p className="text-muted">{hint}</p>}
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  )
}
