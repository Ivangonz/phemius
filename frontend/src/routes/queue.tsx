import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/queue")({
  component: QueuePage,
  errorComponent: RouteError,
})

function QueuePage() {
  return (
    <PageHeader
      title="Queue"
      description="Documents waiting for a script or a voice will appear here."
    />
  )
}
