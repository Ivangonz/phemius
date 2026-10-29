import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { ScriptModelSection } from "@/components/settings/ScriptModelSection"
import { SettingsColumns } from "@/components/settings/SettingsColumns"

export const Route = createFileRoute("/settings/")({
  component: ModelsAndVoicesPage,
  errorComponent: RouteError,
})

function ModelsAndVoicesPage() {
  return (
    <SettingsColumns
      left={<ScriptModelSection />}
      right={<p className="text-muted">The voice section will appear here.</p>}
    />
  )
}
