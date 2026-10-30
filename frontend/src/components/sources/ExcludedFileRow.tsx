import { Button } from "@/components/ui/Button"
import type { SourceExclusion } from "@/hooks/useSourceExclusions"

type ExcludedFileRowProps = {
  exclusion: SourceExclusion
  isBusy: boolean
  onReimport: (exclusion: SourceExclusion) => void
}

export function ExcludedFileRow({
  exclusion,
  isBusy,
  onReimport,
}: ExcludedFileRowProps) {
  const { name, item_key: itemKey } = exclusion

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2.5">
      <div className="min-w-0">
        <p className="font-medium wrap-anywhere">{name}</p>
        {itemKey !== name && (
          <p className="font-mono text-small wrap-anywhere text-muted">
            {itemKey}
          </p>
        )}
      </div>
      <Button
        variant="secondary"
        disabled={isBusy}
        onClick={() => onReimport(exclusion)}
      >
        Re-import<span className="sr-only"> {name}</span>
      </Button>
    </li>
  )
}
