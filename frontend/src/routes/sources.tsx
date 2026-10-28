import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/sources")({
  component: SourcesPage,
  errorComponent: RouteError,
})

function SourcesPage() {
  return (
    <PageHeader
      title="Sources"
      description="Watched folders and connected sources will appear here."
    />
  )
}
