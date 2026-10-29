import { useId } from "react"
import { Link } from "@tanstack/react-router"
import type { SetupCheck } from "@/hooks/useSetupChecks"
import { settingsPathFor } from "@/lib/setupChecks"
import { CheckStatusTag } from "./CheckStatusTag"

export function SetupCheckRow({ check }: { check: SetupCheck }) {
  const labelId = useId()
  const isOk = check.status === "ok"
  const hint = isOk ? null : check.hint
  const canFixInModels =
    check.status === "needs_attention" &&
    settingsPathFor(check.id) === "/settings"

  return (
    <li
      aria-labelledby={labelId}
      className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 border-t border-line py-3"
    >
      <div className="min-w-0 flex-[1_1_14rem]">
        <p id={labelId} className="font-medium">
          {check.label}
        </p>
        <p className="mt-0.5 text-secondary leading-snug wrap-anywhere text-muted">
          {check.detail}
        </p>
        {hint && <p className="mt-0.5 text-secondary leading-snug">{hint}</p>}
        {canFixInModels && (
          <Link
            to="/settings"
            className="inline-flex min-h-11 items-center text-secondary font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
          >
            Fix in Models and voices
          </Link>
        )}
      </div>
      <CheckStatusTag status={check.status} />
    </li>
  )
}
