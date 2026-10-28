import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
  errorComponent: RouteError,
})

function SettingsPage() {
  return (
    <PageHeader
      title="Settings"
      description="Script model, voice and access settings will appear here."
    />
  )
}
