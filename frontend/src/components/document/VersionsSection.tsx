import type { UseQueryResult } from "@tanstack/react-query"
import { ListError } from "@/components/library/ListError"
import type { components } from "@/lib/api-schema"
import { isDocumentChanged, listAudioVersions } from "@/lib/audioVersions"

type VersionPage = components["schemas"]["Page_VersionSummary_"]

type VersionsSectionProps = {
  result: UseQueryResult<VersionPage>
}

const PANEL_CLASSES =
  "flex min-w-0 flex-[2_1_560px] flex-col gap-5 rounded-panel border border-line bg-surface p-4 md:p-5.5"

export function VersionsSection({ result }: VersionsSectionProps) {
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

  return (
    <section aria-label="Audio versions" className={PANEL_CLASSES}>
      {isDocumentChanged(page.items) && (
        <p className="rounded-control bg-warning px-3.5 py-3 text-warning-ink">
          This document changed since its last audio. The newest text has no
          audio yet.
        </p>
      )}
      {versions.length === 0 && (
        <p className="text-muted">No audio yet for this document.</p>
      )}
    </section>
  )
}
