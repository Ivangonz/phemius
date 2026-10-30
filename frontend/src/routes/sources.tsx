import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { SourcesPage } from "@/components/sources/SourcesPage"

export const Route = createFileRoute("/sources")({
  component: SourcesPage,
  errorComponent: RouteError,
})
