import { useId } from "react"
import type { AccessMode } from "@/hooks/useAccess"
import { useUpdateSettings } from "@/hooks/useSettings"
import { getErrorMessage } from "@/lib/api"
import { RestartNote } from "./RestartNote"

type ModeOption = { mode: AccessMode; label: string; description: string }

const MODE_OPTIONS: ModeOption[] = [
  {
    mode: "local",
    label: "This computer only",
    description: "Safest. Only you can open it, from this machine.",
  },
  {
    mode: "network",
    label: "Anyone on my network",
    description:
      "Teammates or your phone can open it. Requires the access token.",
  },
  {
    mode: "proxy",
    label: "Behind my own proxy or domain",
    description: "For a server with HTTPS in front. Requires the access token.",
  },
]

type AccessModeFieldProps = {
  savedMode: AccessMode
  activeMode: AccessMode
  isLocked: boolean
}

export function AccessModeField({
  savedMode,
  activeMode,
  isLocked,
}: AccessModeFieldProps) {
  const updateSettings = useUpdateSettings()
  const lockedId = useId()
  const pendingMode = updateSettings.isPending
    ? updateSettings.variables.access_mode
    : undefined
  const selectedMode = pendingMode ?? savedMode

  function handleChange(mode: AccessMode) {
    updateSettings.mutate({ access_mode: mode })
  }

  return (
    <div className="flex flex-col gap-3">
      <fieldset
        disabled={isLocked}
        aria-describedby={isLocked ? lockedId : undefined}
        className="flex flex-col gap-2"
      >
        <legend className="sr-only">Network access</legend>
        {MODE_OPTIONS.map((option) => (
          <label
            key={option.mode}
            className="flex min-h-11 cursor-pointer items-start gap-2.5 rounded-control border border-line bg-surface p-3 has-checked:border-primary has-checked:bg-selected has-disabled:cursor-not-allowed"
          >
            <input
              type="radio"
              name="access-mode"
              value={option.mode}
              checked={selectedMode === option.mode}
              onChange={() => handleChange(option.mode)}
              className="mt-0.5 size-4.5 flex-none accent-primary"
            />
            <span className="flex flex-col gap-0.5">
              <span className="font-semibold">{option.label}</span>
              <span className="text-secondary leading-snug text-muted">
                {option.description}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {isLocked && (
        <p id={lockedId} className="text-secondary text-muted">
          The mode is set by PHEMIUS_ACCESS_MODE. Change the variable and
          restart Phemius to choose another.
        </p>
      )}
      {updateSettings.isError && (
        <p role="alert" className="text-secondary text-danger-ink">
          Could not save the mode: {getErrorMessage(updateSettings.error)}
        </p>
      )}
      {savedMode !== activeMode && <RestartNote activeMode={activeMode} />}
    </div>
  )
}
