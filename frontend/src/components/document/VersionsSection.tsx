import type { UseQueryResult } from "@tanstack/react-query"
import { ListError } from "@/components/library/ListError"
import type { components } from "@/lib/api-schema"
import { isDocumentChanged, listAudioVersions } from "@/lib/audioVersions"
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
  const selected =
    versions.find((version) => version.id === selectedId) ?? versions[0]

  return (
    <section aria-label="Audio versions" className={PANEL_CLASSES}>
      {isDocumentChanged(page.items) && (
        <p className="rounded-control bg-warning px-3.5 py-3 text-warning-ink">
          This document changed since its last audio. Generate a version to hear
          the newest text.
        </p>
      )}
      {selected ? (
        <>
          <VersionList
            versions={versions}
            selectedId={selected.id}
            onSelect={onSelect}
          />
          <VersionDetail key={selected.id} version={selected} title={title} />
        </>
      ) : (
        <p className="text-muted">No audio yet for this document.</p>
      )}
    </section>
  )
}
