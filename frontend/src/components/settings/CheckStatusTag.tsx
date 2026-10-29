import type { SetupCheck } from "@/hooks/useSetupChecks"
import { CHECK_STATUS_LABELS } from "@/lib/setupChecks"

type CheckStatus = SetupCheck["status"]

const STATUS_CLASSES: Record<CheckStatus, string> = {
  ok: "bg-success text-success-ink",
  optional: "bg-chip text-chip-ink",
  needs_attention: "bg-warning text-warning-ink",
}

const STATUS_ICONS: Record<CheckStatus, string> = {
  ok: "M5 12.5l4.5 4.5L19 7.5",
  optional: "M6 12h12",
  needs_attention: "M12 6v7M12 17.5v.5",
}

export function CheckStatusTag({ status }: { status: CheckStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-small font-semibold whitespace-nowrap ${STATUS_CLASSES[status]}`}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d={STATUS_ICONS[status]} />
      </svg>
      {CHECK_STATUS_LABELS[status]}
    </span>
  )
}
