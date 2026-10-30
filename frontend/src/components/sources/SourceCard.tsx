import { useId } from "react"
import { StatusBadge } from "@/components/library/StatusBadge"
import type { SourceView } from "@/hooks/useSources"
import {
  describeFileTypes,
  describeLastSync,
  folderPath,
  kindLabel,
  sourceStatus,
} from "@/lib/sourceDetails"
import { SourceActions } from "./SourceActions"

type SourceCardProps = { source: SourceView }

export function SourceCard({ source }: SourceCardProps) {
  const titleId = useId()
  const status = sourceStatus(source)
  const path = folderPath(source)

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-wrap items-center gap-x-6 gap-y-3.5 rounded-panel border border-line bg-surface px-5 py-4.5"
    >
      <div className="min-w-0 flex-[1_1_18rem]">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-small font-semibold tracking-wider text-muted uppercase">
            {kindLabel(source.kind)}
          </span>
          <StatusBadge label={status.label} kind={status.kind} />
        </div>
        <h2 id={titleId} className="mt-1.5 mb-2 text-lg font-semibold">
          {source.name}
        </h2>
        <div className="text-secondary leading-relaxed text-muted">
          {path && <p className="font-mono wrap-anywhere">{path}</p>}
          <p>{describeLastSync(source.last_sync)}</p>
          {source.error && (
            <p className="text-danger-ink">Last sync failed: {source.error}</p>
          )}
          <p>{describeFileTypes(source)}</p>
        </div>
      </div>
      <SourceActions source={source} />
    </section>
  )
}
