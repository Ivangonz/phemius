import { useId, useRef, useState } from "react"
import { LibraryPager } from "@/components/library/LibraryPager"
import {
  EXCLUSION_PAGE_SIZE,
  useReimportFile,
  useSourceExclusions,
  type SourceExclusion,
} from "@/hooks/useSourceExclusions"
import type { SourceView } from "@/hooks/useSources"
import { getErrorMessage } from "@/lib/api"
import { ExcludedFileRow } from "./ExcludedFileRow"

type ExcludedFilesProps = {
  source: SourceView
  onSyncStarted: (source: SourceView) => void
}

export function ExcludedFiles({ source, onSyncStarted }: ExcludedFilesProps) {
  const titleId = useId()
  const heading = useRef<HTMLHeadingElement>(null)
  const [offset, setOffset] = useState(0)
  const [restored, setRestored] = useState<string | null>(null)
  const exclusions = useSourceExclusions(source.id, offset)
  const reimport = useReimportFile(source.id, (exclusion) => {
    setRestored(exclusion.name)
    // The server syncs an active source right away.
    if (source.status === "active") onSyncStarted(source)
  })
  const page = exclusions.data
  const error = exclusions.error ?? reimport.error
  const isPastEnd = page !== undefined && !page.items.length && page.offset > 0
  const isEmpty = page !== undefined && !page.items.length && page.offset === 0
  const hasItems = page !== undefined && page.items.length > 0

  if (isPastEnd && offset === page.offset)
    setOffset(Math.max(0, offset - EXCLUSION_PAGE_SIZE))

  function handleReimport(exclusion: SourceExclusion) {
    reimport.mutate(exclusion, { onSettled: () => heading.current?.focus() })
  }

  return (
    <section
      aria-labelledby={titleId}
      className="flex min-w-0 flex-[1_1_18rem] flex-col gap-2 rounded-control border border-line bg-surface-subtle p-4"
    >
      <h3 id={titleId} ref={heading} tabIndex={-1} className="font-semibold">
        Excluded files
      </h3>
      <p className="text-secondary text-muted">
        Files deleted from the library are skipped on every sync. A re-imported
        file comes back on the next sync.
      </p>
      <p role="status" className="text-secondary">
        {restored && `${restored} imports on the next sync.`}
      </p>
      {error && (
        <p role="alert" className="text-secondary text-danger-ink">
          Error: {getErrorMessage(error)}
        </p>
      )}
      {(isPastEnd || (!page && !exclusions.isError)) && (
        <p className="text-muted">Loading excluded files…</p>
      )}
      {isEmpty && <p className="text-muted">No excluded files.</p>}
      {page && hasItems && (
        <>
          <ul className="divide-y divide-line">
            {page.items.map((exclusion) => (
              <ExcludedFileRow
                key={exclusion.id}
                exclusion={exclusion}
                isBusy={reimport.isPending}
                onReimport={handleReimport}
              />
            ))}
          </ul>
          <LibraryPager
            offset={page.offset}
            shown={page.items.length}
            total={page.total}
            onPrevious={() =>
              setOffset(Math.max(0, offset - EXCLUSION_PAGE_SIZE))
            }
            onNext={() => setOffset(offset + EXCLUSION_PAGE_SIZE)}
          />
        </>
      )}
    </section>
  )
}
