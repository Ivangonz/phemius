import { createFileRoute } from "@tanstack/react-router"
import { QueuePage } from "@/components/queue/QueuePage"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/queue")({
  component: QueuePage,
  errorComponent: RouteError,
})
