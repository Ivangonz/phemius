import { useId } from "react"
import { Link } from "@tanstack/react-router"

export function EmptyQueue() {
  const titleId = useId()

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col items-center gap-2 rounded-panel border border-dashed border-line-dashed bg-surface px-6 py-12 text-center"
    >
      <h2 id={titleId} className="text-lg font-semibold">
        Nothing in the queue
      </h2>
      <p className="max-w-md text-muted">
        Documents you send for audio from the{" "}
        <Link to="/" className="font-medium text-primary underline">
          Library
        </Link>{" "}
        wait here while their script is written and narrated.
      </p>
    </section>
  )
}
