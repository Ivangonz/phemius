import { useId, useState } from "react"
import { FilterSelect } from "@/components/library/FilterSelect"
import { LibraryPager } from "@/components/library/LibraryPager"
import {
  ACTIVITY_PAGE_SIZE,
  useSourceActivity,
} from "@/hooks/useSourceActivity"
import { useSources, type SourceView } from "@/hooks/useSources"
import { getErrorMessage } from "@/lib/api"
import { ActivityList } from "./ActivityList"

type SourceActivityProps = {
  isSyncing: (source: SourceView) => boolean
  isPolling: boolean
}

export function SourceActivity({ isSyncing, isPolling }: SourceActivityProps) {
  const titleId = useId()
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)
  const sources = useSources(isSyncing)
  const activity = useSourceActivity({ sourceId, offset }, isPolling)
  const page = activity.data
  const isLoading = !page && !activity.isError
  const options = [
    { value: "", label: "All sources" },
    ...(sources.data?.items ?? []).map((source) => ({
      value: String(source.id),
      label: source.name,
    })),
  ]

  function handleSourceChange(value: string) {
    setSourceId(value ? Number(value) : null)
    setOffset(0)
  }

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-3 rounded-panel border border-line bg-surface p-5"
    >
      <h2 id={titleId} className="text-lg font-semibold">
        Recent activity
      </h2>
      <FilterSelect
        label="Source"
        value={sourceId === null ? "" : String(sourceId)}
        options={options}
        onChange={handleSourceChange}
      />
      {activity.isError && (
        <p role="alert" className="text-danger-ink">
          Could not load activity: {getErrorMessage(activity.error)}
        </p>
      )}
      {isLoading && (
        <p role="status" className="text-muted">
          Loading activity…
        </p>
      )}
      {page && (
        <>
          <ActivityList entries={page.items} />
          <LibraryPager
            offset={page.offset}
            shown={page.items.length}
            total={page.total}
            onPrevious={() =>
              setOffset(Math.max(0, offset - ACTIVITY_PAGE_SIZE))
            }
            onNext={() => setOffset(offset + ACTIVITY_PAGE_SIZE)}
          />
        </>
      )}
    </section>
  )
}
