import { createFileRoute } from "@tanstack/react-router"
import { DocumentNotFound } from "@/components/document/DocumentNotFound"
import { DocumentPage } from "@/components/document/DocumentPage"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/docs/$documentId")({
  component: DocumentRoute,
  errorComponent: RouteError,
})

function parseDocumentId(value: string): number | null {
  if (!/^\d{1,15}$/.test(value)) return null
  const id = Number(value)
  return id > 0 ? id : null
}

function DocumentRoute() {
  const { documentId } = Route.useParams()
  const id = parseDocumentId(documentId)
  if (id === null) return <DocumentNotFound />
  return <DocumentPage key={id} documentId={id} />
}
