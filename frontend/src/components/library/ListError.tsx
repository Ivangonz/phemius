import { Button } from "@/components/ui/Button"
import { ApiError, getErrorMessage } from "@/lib/api"

type ListErrorProps = {
  title: string
  error: unknown
  onRetry: () => void
}

export function ListError({ title, error, onRetry }: ListErrorProps) {
  const hint = error instanceof ApiError ? error.hint : undefined

  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 rounded-panel border border-danger-line bg-surface p-5"
    >
      <p className="font-semibold text-danger-ink">{title}</p>
      <p>{getErrorMessage(error)}</p>
      {hint && <p className="text-muted">{hint}</p>}
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  )
}
