import { ApiError, getErrorMessage } from "@/lib/api"

export function ChecksError({ error }: { error: unknown }) {
  const hint = error instanceof ApiError ? error.hint : undefined

  return (
    <div
      role="alert"
      className="rounded-control border border-danger-line bg-danger px-3.5 py-3 text-secondary text-danger-ink"
    >
      <p className="font-semibold">The checks could not run.</p>
      <p>{getErrorMessage(error)}</p>
      {hint && <p>{hint}</p>}
    </div>
  )
}
