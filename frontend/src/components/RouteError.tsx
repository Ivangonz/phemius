import { useRouter, type ErrorComponentProps } from "@tanstack/react-router"
import { ApiError, getErrorMessage } from "@/lib/api"
import { Button } from "@/components/ui/Button"

export function RouteError({ error, reset }: ErrorComponentProps) {
  const router = useRouter()
  const hint = error instanceof ApiError ? error.hint : undefined

  function handleRetry() {
    reset()
    void router.invalidate()
  }

  return (
    <section
      role="alert"
      className="flex flex-col items-start gap-3 rounded-panel border border-danger-line bg-surface p-6"
    >
      <h1 className="text-title">Something went wrong</h1>
      <p>{getErrorMessage(error)}</p>
      {hint && <p className="text-muted">{hint}</p>}
      <Button onClick={handleRetry}>Try again</Button>
    </section>
  )
}
