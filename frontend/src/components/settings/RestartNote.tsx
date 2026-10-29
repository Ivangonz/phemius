import type { AccessMode } from "@/hooks/useAccess"

const MODE_NAMES: Record<AccessMode, string> = {
  local: "this computer only",
  network: "anyone on my network",
  proxy: "behind my own proxy or domain",
}

type RestartNoteProps = { activeMode: AccessMode }

export function RestartNote({ activeMode }: RestartNoteProps) {
  return (
    <p
      role="status"
      className="rounded-control border border-line bg-surface-subtle px-3.5 py-3 text-secondary leading-relaxed"
    >
      <strong className="font-semibold">Restart Phemius to apply.</strong> It
      still runs as “{MODE_NAMES[activeMode]}” until then. Stop the server and
      start it again with <code className="font-mono">phemius serve</code>.
    </p>
  )
}
