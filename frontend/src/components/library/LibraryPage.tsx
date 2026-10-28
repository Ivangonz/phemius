import { PageHeader } from "@/components/PageHeader"
import { useDocuments } from "@/hooks/useDocuments"
import {
  hasFilters,
  toDocumentQuery,
  type LibrarySearch,
} from "@/lib/librarySearch"
import { LibraryFilters } from "./LibraryFilters"
import { LibraryResults } from "./LibraryResults"

const NO_FILTERS = {
  q: undefined,
  category: undefined,
  tone: undefined,
  status: undefined,
}

function describeCount(total: number | undefined): string {
  if (total === undefined) return "Loading your documents…"
  return total === 1 ? "1 document" : `${total} documents`
}

type LibraryPageProps = {
  search: LibrarySearch
  onSearchChange: (patch: Partial<LibrarySearch>) => void
}

export function LibraryPage({ search, onSearchChange }: LibraryPageProps) {
  const result = useDocuments(toDocumentQuery(search))
  const currentPage = search.page ?? 1

  return (
    <>
      <PageHeader
        title="Library"
        description={describeCount(result.data?.total)}
      />
      <LibraryFilters search={search} onChange={onSearchChange} />
      <LibraryResults
        result={result}
        isFiltered={hasFilters(search)}
        onClearFilters={() => onSearchChange(NO_FILTERS)}
        onPageChange={(delta) => onSearchChange({ page: currentPage + delta })}
      />
    </>
  )
}
