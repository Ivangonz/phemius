import { ApiError, getErrorMessage } from "@/lib/api"

type SaveErrorProps = { error: unknown }

export function SaveError({ error }: SaveErrorProps) {
  const isApiError = error instanceof ApiError
  const detail = isApiError ? error.message : getErrorMessage(error)

  return (
    <div role="alert" className="flex flex-col gap-0.5 text-secondary">
      <p className="font-semibold text-danger-ink">Not saved: {detail}</p>
      {isApiError && error.hint && <p>{error.hint}</p>}
    </div>
  )
}
