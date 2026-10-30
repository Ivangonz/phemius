import { Link } from "@tanstack/react-router"

export function DocumentNotFound() {
  return (
    <section className="flex flex-col items-start gap-3">
      <h1 className="text-title">Document not found</h1>
      <p className="text-muted">
        It may have been deleted, or the address is wrong.
      </p>
      <Link
        to="/"
        className="inline-flex min-h-11 items-center font-medium text-primary underline-offset-4 hover:text-primary-hover hover:underline"
      >
        Go to the library
      </Link>
    </section>
  )
}
