import { useCallback } from "react"
import { useLibraryConfig } from "@/hooks/useLibraryConfig"
import { STATUS_LABELS } from "@/lib/documentStatus"
import {
  CATEGORIES,
  DOCUMENT_STATUSES,
  parseOrder,
  parseStatus,
  type LibrarySearch,
} from "@/lib/librarySearch"
import { FilterSelect, type FilterOption } from "./FilterSelect"
import { SearchField } from "./SearchField"

const CATEGORY_OPTIONS: FilterOption[] = [
  { value: "", label: "All categories" },
  ...CATEGORIES.map((category) => ({ value: category, label: category })),
]

const STATUS_OPTIONS: FilterOption[] = [
  { value: "", label: "Any status" },
  ...DOCUMENT_STATUSES.map((status) => ({
    value: status,
    label: STATUS_LABELS[status],
  })),
]

const ORDER_OPTIONS: FilterOption[] = [
  { value: "-created", label: "Newest first" },
  { value: "created", label: "Oldest first" },
  { value: "-updated", label: "Recently updated" },
  { value: "title", label: "Title A to Z" },
]

function toneOptions(tones: Record<string, string> | undefined) {
  const names = Object.keys(tones ?? {})
  return [
    { value: "", label: "Any tone" },
    ...names.map((tone) => ({ value: tone, label: tone })),
  ]
}

type LibraryFiltersProps = {
  search: LibrarySearch
  onChange: (patch: Partial<LibrarySearch>) => void
}

export function LibraryFilters({ search, onChange }: LibraryFiltersProps) {
  const { data: config } = useLibraryConfig()
  const handleSearch = useCallback(
    (q: string) => onChange({ q: q || undefined }),
    [onChange],
  )

  return (
    <div
      role="search"
      aria-label="Filter documents"
      className="grid grid-cols-2 gap-3 md:grid-cols-[minmax(12rem,2fr)_repeat(4,minmax(0,1fr))]"
    >
      <div className="col-span-2 md:col-span-1">
        <SearchField value={search.q ?? ""} onSearch={handleSearch} />
      </div>
      <FilterSelect
        label="Category"
        value={search.category ?? ""}
        options={CATEGORY_OPTIONS}
        onChange={(category) => onChange({ category: category || undefined })}
      />
      <FilterSelect
        label="Tone"
        value={search.tone ?? ""}
        options={toneOptions(config?.tones)}
        onChange={(tone) => onChange({ tone: tone || undefined })}
      />
      <FilterSelect
        label="Status"
        value={search.status ?? ""}
        options={STATUS_OPTIONS}
        onChange={(status) => onChange({ status: parseStatus(status) })}
      />
      <FilterSelect
        label="Sort by"
        value={search.order ?? "-created"}
        options={ORDER_OPTIONS}
        onChange={(order) => onChange({ order: parseOrder(order) })}
      />
    </div>
  )
}
