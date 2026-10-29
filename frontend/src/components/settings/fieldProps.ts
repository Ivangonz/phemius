export const INPUT_CLASSES =
  "min-h-11 min-w-0 flex-[1_1_14rem] rounded-control border border-line-control bg-surface px-3 font-mono text-ink disabled:cursor-not-allowed disabled:bg-page disabled:text-muted"

type FieldNotes = { isLocked?: boolean; description?: unknown; error?: string }

// The ids FieldShell gives each note under a control, for aria-describedby.
export function describedBy(id: string, notes: FieldNotes): string | undefined {
  const ids = [
    notes.isLocked ? `${id}-locked` : "",
    notes.description ? `${id}-description` : "",
    notes.error ? `${id}-error` : "",
  ].filter(Boolean)
  return ids.length ? ids.join(" ") : undefined
}
