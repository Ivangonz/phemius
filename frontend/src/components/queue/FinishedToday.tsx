import { useId } from "react"
import { useFinishedToday } from "@/hooks/useQueue"
import { getErrorMessage } from "@/lib/api"
import { FinishedRow } from "./FinishedRow"

const PANEL_CLASSES =
  "overflow-hidden rounded-panel border border-line bg-surface"

export function FinishedToday() {
  const headingId = useId()
  const { data: jobs, error, isError } = useFinishedToday()

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h2
        id={headingId}
        className="mt-2.5 text-secondary font-semibold tracking-wide text-muted uppercase"
      >
        Finished today
      </h2>
      {isError && <p role="alert">{getErrorMessage(error)}</p>}
      {jobs?.length === 0 && (
        <p className="text-muted">Nothing has finished yet today.</p>
      )}
      {jobs && jobs.length > 0 && (
        <ul
          aria-labelledby={headingId}
          className={`divide-y divide-line ${PANEL_CLASSES}`}
        >
          {jobs.map((job) => (
            <li key={job.id}>
              <FinishedRow job={job} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
