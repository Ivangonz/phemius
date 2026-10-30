import { useState } from "react"
import { ListError } from "@/components/library/ListError"
import { useDocument, useDocumentVersions } from "@/hooks/useDocument"
import { ApiError } from "@/lib/api"
import { DocumentHeader } from "./DocumentHeader"
import { DocumentNotFound } from "./DocumentNotFound"
import { GeneratePanel } from "./GeneratePanel"
import { VersionsSection } from "./VersionsSection"

export function DocumentPage({ documentId }: { documentId: number }) {
  const document = useDocument(documentId)
  const versions = useDocumentVersions(documentId)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  if (!document.data) {
    if (document.error instanceof ApiError && document.error.status === 404)
      return <DocumentNotFound />
    if (document.isError)
      return (
        <ListError
          title="This document could not be loaded."
          error={document.error}
          onRetry={() => document.refetch()}
        />
      )
    return (
      <p role="status" className="text-muted">
        Loading the document…
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-5.5">
      <DocumentHeader document={document.data} />
      <div className="flex flex-wrap items-start gap-5">
        <VersionsSection
          result={versions}
          title={document.data.title}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <GeneratePanel document={document.data} onQueued={setSelectedId} />
      </div>
    </div>
  )
}
