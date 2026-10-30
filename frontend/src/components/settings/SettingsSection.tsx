import type { ReactNode } from "react"
import { Button } from "@/components/ui/Button"
import { useSettings, type SettingsOverview } from "@/hooks/useSettings"
import { ApiError, getErrorMessage } from "@/lib/api"

type SettingsSectionProps = {
  id: string
  title: string
  description: string
  children: (overview: SettingsOverview) => ReactNode
}

// A settings card that loads the saved settings before showing its form.
export function SettingsSection({
  id,
  title,
  description,
  children,
}: SettingsSectionProps) {
  const settings = useSettings()

  return (
    <section
      aria-labelledby={id}
      className="flex min-w-0 flex-col gap-4.5 rounded-panel border border-line bg-surface p-5.5"
    >
      <div>
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        <p className="mt-1 text-secondary text-muted">{description}</p>
      </div>
      {settings.isPending && <p className="text-muted">Loading settings…</p>}
      {settings.isError && (
        <div role="alert" className="flex flex-col items-start gap-2">
          <p className="font-semibold text-danger-ink">
            Settings could not be loaded: {getErrorMessage(settings.error)}
          </p>
          {settings.error instanceof ApiError && settings.error.hint && (
            <p className="text-muted">{settings.error.hint}</p>
          )}
          <Button variant="secondary" onClick={() => void settings.refetch()}>
            Try again
          </Button>
        </div>
      )}
      {settings.data && children(settings.data)}
    </section>
  )
}
