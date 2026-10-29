import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { SettingsColumns } from "@/components/settings/SettingsColumns"
import { SetupChecksCard } from "@/components/settings/SetupChecksCard"

export const Route = createFileRoute("/settings/server")({
  component: ServerPage,
  errorComponent: RouteError,
})

function ServerPage() {
  return (
    <SettingsColumns
      left={<p className="text-muted">The access card will appear here.</p>}
      right={
        <>
          <SetupChecksCard />
          <p className="text-muted">Library maintenance will appear here.</p>
        </>
      }
    />
  )
}
