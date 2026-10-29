import { useId } from "react"
import { useAccessStatus, type AccessMode } from "@/hooks/useAccess"
import { useSettings, type SettingsOverview } from "@/hooks/useSettings"
import { getErrorMessage } from "@/lib/api"
import { AccessModeField } from "./AccessModeField"
import { AccessTokenField } from "./AccessTokenField"
import { PortField } from "./PortField"

const ACCESS_MODES: readonly string[] = ["local", "network", "proxy"]

function isAccessMode(value: unknown): value is AccessMode {
  return typeof value === "string" && ACCESS_MODES.includes(value)
}

function savedAccessMode(settings: SettingsOverview, fallback: AccessMode) {
  const value = settings.values.access_mode?.value
  return isAccessMode(value) ? value : fallback
}

export function AccessCard() {
  const titleId = useId()
  const access = useAccessStatus()
  const settings = useSettings()
  const error = access.error ?? settings.error

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-panel border border-line bg-surface p-5.5"
    >
      <div>
        <h2 id={titleId} className="text-lg font-semibold">
          Access
        </h2>
        <p className="mt-1 text-secondary text-muted">
          Who can open Phemius in a browser.
        </p>
      </div>
      {error ? (
        <p role="alert" className="text-danger-ink">
          Could not load access settings: {getErrorMessage(error)}
        </p>
      ) : access.data && settings.data ? (
        <>
          <AccessModeField
            savedMode={savedAccessMode(settings.data, access.data.active_mode)}
            activeMode={access.data.active_mode}
            isLocked={settings.data.values.access_mode?.is_locked ?? false}
          />
          <div className="flex flex-wrap gap-4">
            <PortField port={access.data.port} />
            <AccessTokenField status={access.data} />
          </div>
        </>
      ) : (
        <p role="status" className="text-muted">
          Loading access settings…
        </p>
      )}
      <p className="rounded-control bg-warning px-3.5 py-3 text-secondary leading-relaxed text-warning-ink">
        <strong className="font-semibold">Phemius has no user accounts.</strong>{" "}
        If you open it beyond this computer, keep the access token on and put it
        behind HTTPS.
      </p>
    </section>
  )
}
