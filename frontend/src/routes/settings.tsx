import { createFileRoute, Outlet } from "@tanstack/react-router"
import { PageHeader } from "@/components/PageHeader"
import { RouteError } from "@/components/RouteError"
import { SettingsTabs } from "@/components/settings/SettingsTabs"

export const Route = createFileRoute("/settings")({
  component: SettingsLayout,
  errorComponent: RouteError,
})

function SettingsLayout() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Settings"
        description="Bring your own model and voice, and run Phemius on your own machine or server."
      />
      <SettingsTabs />
      <Outlet />
    </div>
  )
}
