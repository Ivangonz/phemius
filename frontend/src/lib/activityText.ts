import type { components } from "./api-schema"

type ActivityEntry = components["schemas"]["ActivityEntry"]

const ACTION_LABELS: Record<ActivityEntry["action"], string> = {
  imported: "Imported",
  updated: "Updated",
  skipped: "Skipped",
  failed: "Failed",
  reimport: "Brought back",
}

export function describeActivity(entry: ActivityEntry): string {
  const what = entry.item
    ? `${ACTION_LABELS[entry.action]} ${entry.item}.`
    : `${ACTION_LABELS[entry.action]}.`
  return `${entry.source_name}: ${what} ${entry.detail}`
}

// Today shows the time, like a clock; older entries show the day.
export function activityTime(created: number, now: Date): string {
  const when = new Date(created * 1000)
  if (when.toDateString() === now.toDateString())
    return when.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    })
  return when.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}
