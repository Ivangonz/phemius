import { useId } from "react"
import { Link } from "@tanstack/react-router"

export function EmptyLibrary() {
  const titleId = useId()

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col items-center gap-2 rounded-panel border border-dashed border-line-dashed bg-surface px-6 py-12 text-center"
    >
      <h2 id={titleId} className="text-lg font-semibold">
        Your library is empty
      </h2>
      <p className="max-w-md text-muted">
        Choose Upload documents or drop files anywhere on this page. Phemius
        writes a spoken script for each one and narrates it. Markdown, text,
        reStructuredText, HTML, Word and PDF files work.
      </p>
      <p className="max-w-md text-muted">
        You can also watch a folder from{" "}
        <Link to="/sources" className="font-medium text-primary underline">
          Sources
        </Link>
        .
      </p>
    </section>
  )
}
