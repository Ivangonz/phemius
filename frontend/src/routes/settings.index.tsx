import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { SettingsColumns } from "@/components/settings/SettingsColumns"

export const Route = createFileRoute("/settings/")({
  component: ModelsAndVoicesPage,
  errorComponent: RouteError,
})

function ModelsAndVoicesPage() {
  return (
    <SettingsColumns
      left={
        <p className="text-muted">The script model section will appear here.</p>
      }
      right={<p className="text-muted">The voice section will appear here.</p>}
    />
  )
}
