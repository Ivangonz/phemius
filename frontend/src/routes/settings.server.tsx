import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { AccessCard } from "@/components/settings/AccessCard"
import { SettingsColumns } from "@/components/settings/SettingsColumns"
import { SetupChecksCard } from "@/components/settings/SetupChecksCard"

export const Route = createFileRoute("/settings/server")({
  component: ServerPage,
  errorComponent: RouteError,
})

function ServerPage() {
  return (
    <SettingsColumns
      left={<AccessCard />}
      right={
        <>
          <SetupChecksCard />
          <p className="text-muted">Library maintenance will appear here.</p>
        </>
      }
    />
  )
}
