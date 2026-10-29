import { useId } from "react"
import { Button } from "@/components/ui/Button"
import {
  useRunSetupChecks,
  useSetupChecks,
  type SetupCheckRun,
} from "@/hooks/useSetupChecks"
import { formatRunTime } from "@/lib/setupChecks"
import { ChecksError } from "./ChecksError"
import { SetupCheckRow } from "./SetupCheckRow"

function describeRun(run: SetupCheckRun | undefined, isRunning: boolean) {
  if (isRunning) return "Running checks…"
  if (!run) return "The checks have not run yet."
  return `Last run at ${formatRunTime(run.ran_at)}.`
}

export function SetupChecksCard() {
  const headingId = useId()
  const { data, error, isFetching } = useSetupChecks()
  const run = useRunSetupChecks()
  const isRunning = isFetching || run.isPending
  const shownError = run.error ?? error

  const handleRunChecks = () => {
    run.mutate()
  }

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3.5 rounded-panel border border-line bg-surface p-5.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id={headingId} className="text-lg font-semibold">
            Setup checks
          </h2>
          <p aria-live="polite" className="mt-1 text-secondary text-muted">
            {describeRun(data, isRunning)}
          </p>
        </div>
        <Button onClick={handleRunChecks} disabled={isRunning}>
          Run checks
        </Button>
      </div>
      {shownError && <ChecksError error={shownError} />}
      {data && (
        <ul className="flex flex-col">
          {data.checks.map((check) => (
            <SetupCheckRow key={check.id} check={check} />
          ))}
        </ul>
      )}
    </section>
  )
}
