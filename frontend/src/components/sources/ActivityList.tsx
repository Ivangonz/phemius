import type { ActivityEntry } from "@/hooks/useSourceActivity"
import { activityTime, describeActivity } from "@/lib/activityText"

type ActivityListProps = { entries: ActivityEntry[] }

export function ActivityList({ entries }: ActivityListProps) {
  const now = new Date()

  if (entries.length === 0)
    return <p className="text-muted">Nothing has been imported yet.</p>

  return (
    <ol className="flex flex-col gap-3">
      {entries.map((entry) => (
        <li key={entry.id} className="flex gap-3 text-secondary leading-snug">
          <time
            dateTime={new Date(entry.created * 1000).toISOString()}
            className="w-14 flex-none font-mono text-small text-muted"
          >
            {activityTime(entry.created, now)}
          </time>
          <span className="min-w-0 wrap-anywhere">
            {describeActivity(entry)}
          </span>
        </li>
      ))}
    </ol>
  )
}
