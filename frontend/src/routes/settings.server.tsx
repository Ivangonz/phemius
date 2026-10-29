import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { SettingsColumns } from "@/components/settings/SettingsColumns"

export const Route = createFileRoute("/settings/server")({
  component: ServerPage,
  errorComponent: RouteError,
})

function ServerPage() {
  return (
    <SettingsColumns
      left={<p className="text-muted">The access card will appear here.</p>}
      right={
        <p className="text-muted">
          Setup checks and library maintenance will appear here.
        </p>
      }
    />
  )
}
