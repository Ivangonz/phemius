import { createFileRoute } from "@tanstack/react-router"
import { RouteError } from "@/components/RouteError"
import { ScriptModelSection } from "@/components/settings/ScriptModelSection"
import { SettingsColumns } from "@/components/settings/SettingsColumns"
import { VoiceSection } from "@/components/settings/VoiceSection"

export const Route = createFileRoute("/settings/")({
  component: ModelsAndVoicesPage,
  errorComponent: RouteError,
})

function ModelsAndVoicesPage() {
  return (
    <SettingsColumns left={<ScriptModelSection />} right={<VoiceSection />} />
  )
}
