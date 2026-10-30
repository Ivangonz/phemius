import { Link } from "@tanstack/react-router"

type JobFailureProps = {
  error: string | null
  hint: string | null
}

export function JobFailure({ error, hint }: JobFailureProps) {
  return (
    <p className="rounded-control bg-danger px-3.5 py-3 text-secondary leading-relaxed text-danger-ink">
      {error ?? "The job stopped without an error message."} {hint}{" "}
      <Link to="/settings" className="font-semibold underline">
        Open settings
      </Link>
    </p>
  )
}
