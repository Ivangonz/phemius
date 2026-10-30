import { ListError } from "@/components/library/ListError"
import { useSources, type SourceView } from "@/hooks/useSources"
import { SourceCard } from "./SourceCard"

type SourceListProps = {
  isSyncing: (source: SourceView) => boolean
  onSyncStarted: (source: SourceView) => void
}

export function SourceList({ isSyncing, onSyncStarted }: SourceListProps) {
  const result = useSources(isSyncing)
  const items = result.data?.items

  if (!items) {
    if (result.isError)
      return (
        <ListError
          error={result.error}
          title="Sources could not be loaded."
          onRetry={() => void result.refetch()}
        />
      )
    return (
      <p role="status" className="text-muted">
        Loading sources…
      </p>
    )
  }

  if (items.length === 0)
    return (
      <p className="text-muted">
        No sources yet. Add a folder and Phemius imports what it holds.
      </p>
    )

  return items.map((source) => (
    <SourceCard
      key={source.id}
      source={source}
      isSyncing={isSyncing(source)}
      onSyncStarted={onSyncStarted}
    />
  ))
}
