import { useCallback } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { LibraryPage } from "@/components/library/LibraryPage"
import { RouteError } from "@/components/RouteError"
import { librarySearchSchema, type LibrarySearch } from "@/lib/librarySearch"

export const Route = createFileRoute("/")({
  validateSearch: librarySearchSchema,
  component: LibraryRoute,
  errorComponent: RouteError,
})

function LibraryRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  // Any filter change starts again from the first page.
  const handleSearchChange = useCallback(
    (patch: Partial<LibrarySearch>) =>
      navigate({
        search: (previous) => ({ ...previous, page: undefined, ...patch }),
        replace: true,
      }),
    [navigate],
  )

  return <LibraryPage search={search} onSearchChange={handleSearchChange} />
}
