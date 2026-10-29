import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/docs/$documentId")({
  component: DocumentPage,
  errorComponent: RouteError,
})

function DocumentPage() {
  return (
    <PageHeader
      title="Document"
      description="The script, tone, voice and versions of this document will appear here."
    />
  )
}
