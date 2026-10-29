import { useId } from "react"

type PortFieldProps = { port: number | null }

// The port is chosen when the server starts, so it is shown, not edited.
export function PortField({ port }: PortFieldProps) {
  const inputId = useId()
  const hintId = useId()

  return (
    <div className="flex min-w-0 flex-[1_1_9rem] flex-col gap-1.5">
      <label htmlFor={inputId} className="text-secondary font-semibold">
        Port
      </label>
      <input
        id={inputId}
        type="text"
        inputMode="numeric"
        readOnly
        value={port === null ? "" : String(port)}
        placeholder="Unknown"
        aria-describedby={hintId}
        className="min-h-11 w-full rounded-control border border-line-control bg-surface-subtle px-3 font-mono"
      />
      <p id={hintId} className="text-small text-muted">
        Change it with <code className="font-mono">phemius serve --port</code>{" "}
        or the <code className="font-mono">ports</code> line in
        docker-compose.yml, then restart.
      </p>
    </div>
  )
}
