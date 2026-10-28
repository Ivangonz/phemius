import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/")({
  component: LibraryPage,
  errorComponent: RouteError,
})

function LibraryPage() {
  return (
    <PageHeader
      title="Library"
      description="Your documents and their narrated audio will appear here."
    />
  )
}
