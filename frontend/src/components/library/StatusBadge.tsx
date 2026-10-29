import type { StatusKind } from "@/lib/documentStatus"

const KIND_CLASSES: Record<StatusKind, string> = {
  ready: "bg-success text-success-ink",
  working: "bg-primary-tint text-primary-tint-ink",
  failed: "bg-danger text-danger-ink",
  idle: "bg-chip text-chip-ink",
}

const KIND_ICONS: Record<StatusKind, string> = {
  ready: "M5 12.5l4.5 4.5L19 7.5",
  working: "M12 6v6l4 2",
  failed: "M7 7l10 10M17 7L7 17",
  idle: "M6 12h12",
}

type StatusBadgeProps = {
  label: string
  kind: StatusKind
}

export function StatusBadge({ label, kind }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill px-2 py-0.5 text-small font-medium whitespace-nowrap ${KIND_CLASSES[kind]}`}
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
        <path d={KIND_ICONS[kind]} />
      </svg>
      {label}
    </span>
  )
}
