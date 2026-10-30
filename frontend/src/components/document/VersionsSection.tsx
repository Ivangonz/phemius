import { useCallback, useState } from "react"
import type { UseQueryResult } from "@tanstack/react-query"
import { ListError } from "@/components/library/ListError"
import type { components } from "@/lib/api-schema"
import { isDocumentChanged, listAudioVersions } from "@/lib/audioVersions"
import { CompareVersions } from "./CompareVersions"
import { VersionDetail } from "./VersionDetail"
import { VersionList } from "./VersionList"

type VersionPage = components["schemas"]["Page_VersionSummary_"]

type VersionsSectionProps = {
  result: UseQueryResult<VersionPage>
  title: string
  selectedId: number | null
  onSelect: (audioId: number) => void
}

const PANEL_CLASSES =
  "flex min-w-0 flex-[2_1_560px] flex-col gap-5 rounded-panel border border-line bg-surface p-4 md:p-5.5"

export function VersionsSection({
  result,
  title,
  selectedId,
  onSelect,
}: VersionsSectionProps) {
  const [isComparing, setIsComparing] = useState(false)
  const handleSelect = useCallback(
    (audioId: number) => {
      setIsComparing(false)
      onSelect(audioId)
    },
    [onSelect],
  )
  const page = result.data

  if (!page) {
    if (result.isError)
      return (
        <ListError
          title="The versions could not be loaded."
          error={result.error}
          onRetry={() => result.refetch()}
        />
      )
    return (
      <p role="status" className="text-muted">
        Loading versions…
      </p>
    )
  }

  const versions = listAudioVersions(page.items)
  const [newest, second] = versions
  const selected =
    versions.find((version) => version.id === selectedId) ?? newest
  const comparePair = second && newest ? { first: newest, second } : null

  return (
    <section aria-label="Audio versions" className={PANEL_CLASSES}>
      {isDocumentChanged(page.items) && (
        <p className="rounded-control bg-warning px-3.5 py-3 text-warning-ink">
          This document changed since its last audio. Generate a version to hear
          the newest text.
        </p>
      )}
      {selected ? (
        <div className="flex flex-wrap gap-2">
          <VersionList
            versions={versions}
            selectedId={isComparing ? null : selected.id}
            onSelect={handleSelect}
          />
          {comparePair && (
            <button
              type="button"
              aria-pressed={isComparing}
              onClick={() => setIsComparing(!isComparing)}
              className="min-h-11 cursor-pointer rounded-control border border-dashed border-line-dashed px-4 font-medium text-primary-hover hover:bg-primary-tint"
            >
              Compare two versions
            </button>
          )}
        </div>
      ) : (
        <p className="text-muted">No audio yet for this document.</p>
      )}
      {comparePair && isComparing && (
        <CompareVersions versions={versions} {...comparePair} />
      )}
      {selected && !isComparing && (
        <VersionDetail key={selected.id} version={selected} title={title} />
      )}
    </section>
  )
}
