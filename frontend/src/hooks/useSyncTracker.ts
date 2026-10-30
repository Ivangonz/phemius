import { useCallback, useEffect, useRef, useState } from "react"
import type { SourceView } from "./useSources"

type Baseline = Pick<SourceView, "last_sync" | "error">

// A failed sync that repeats the same error changes nothing we can see, so
// stop calling a source Syncing (and stop polling) after this long.
const SYNC_WATCH_MS = 60_000

// The API has no "syncing" state: a sync runs in the background and is done
// when the source's last sync or error changes from what it was at the click.
export function useSyncTracker() {
  const [pending, setPending] = useState<ReadonlyMap<number, Baseline>>(
    () => new Map(),
  )
  const timers = useRef(new Map<number, number>())

  useEffect(() => {
    const scheduled = timers.current
    return () => scheduled.forEach((timer) => window.clearTimeout(timer))
  }, [])

  const track = useCallback((source: SourceView) => {
    const { id, last_sync, error } = source
    setPending((current) => new Map(current).set(id, { last_sync, error }))
    window.clearTimeout(timers.current.get(id))
    const timer = window.setTimeout(() => {
      timers.current.delete(id)
      setPending((current) => {
        const next = new Map(current)
        next.delete(id)
        return next
      })
    }, SYNC_WATCH_MS)
    timers.current.set(id, timer)
  }, [])

  const isSyncing = useCallback(
    (source: SourceView) => {
      const baseline = pending.get(source.id)
      return (
        baseline !== undefined &&
        source.status === "active" &&
        baseline.last_sync === source.last_sync &&
        baseline.error === source.error
      )
    },
    [pending],
  )

  // Activity keeps refreshing for the whole watch window, since a sync's
  // last imports land just before the source reports it finished.
  return { track, isSyncing, hasPending: pending.size > 0 }
}
