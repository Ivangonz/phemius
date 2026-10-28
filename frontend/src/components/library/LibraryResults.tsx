import type { UseQueryResult } from "@tanstack/react-query"
import type { components } from "@/lib/api-schema"
import { DocumentList } from "./DocumentList"
import { EmptyLibrary } from "./EmptyLibrary"
import { LibraryPager } from "./LibraryPager"
import { ListError } from "./ListError"
import { NoMatches } from "./NoMatches"

type DocumentPage = components["schemas"]["Page_DocumentListItem_"]

type LibraryResultsProps = {
  result: UseQueryResult<DocumentPage>
  isFiltered: boolean
  onClearFilters: () => void
  onPageChange: (delta: number) => void
}

export function LibraryResults({
  result,
  isFiltered,
  onClearFilters,
  onPageChange,
}: LibraryResultsProps) {
  const page = result.data

  if (!page) {
    if (result.isError)
      return <ListError error={result.error} onRetry={() => result.refetch()} />
    return (
      <p role="status" className="text-muted">
        Loading documents…
      </p>
    )
  }

  if (page.items.length === 0)
    return isFiltered ? (
      <NoMatches onClear={onClearFilters} />
    ) : (
      <EmptyLibrary />
    )

  return (
    <>
      <DocumentList documents={page.items} />
      <LibraryPager
        offset={page.offset}
        shown={page.items.length}
        total={page.total}
        onPrevious={() => onPageChange(-1)}
        onNext={() => onPageChange(1)}
      />
    </>
  )
}
