import type { UseQueryResult } from "@tanstack/react-query"
import type { OllamaModelList } from "@/hooks/useScriptModels"
import { ApiError, getErrorMessage } from "@/lib/api"

type OllamaListStatusProps = { query: UseQueryResult<OllamaModelList> }

export function OllamaListStatus({ query }: OllamaListStatusProps) {
  if (query.isPending) return <p>Looking for installed models…</p>
  if (query.isError) {
    const hint = query.error instanceof ApiError ? query.error.hint : undefined
    return (
      <p role="alert" className="text-danger-ink">
        Could not list models: {getErrorMessage(query.error)} {hint}
      </p>
    )
  }
  const count = query.data.models.length
  if (count === 0)
    return <p>No models installed. Run `ollama pull llama3.2`.</p>
  return (
    <p>
      {count} installed {count === 1 ? "model" : "models"} at the saved address.
      Save a new address to list its models.
    </p>
  )
}
