import { Button } from "@/components/ui/Button"

type LibraryPagerProps = {
  offset: number
  shown: number
  total: number
  onPrevious: () => void
  onNext: () => void
}

export function LibraryPager({
  offset,
  shown,
  total,
  onPrevious,
  onNext,
}: LibraryPagerProps) {
  const end = offset + shown
  if (offset === 0 && end >= total) return null

  return (
    <nav
      aria-label="Pages"
      className="flex flex-wrap items-center justify-between gap-3"
    >
      <p className="font-mono text-small text-muted">
        {offset + 1}–{end} of {total}
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          onClick={onPrevious}
          disabled={offset === 0}
        >
          Previous page
        </Button>
        <Button variant="secondary" onClick={onNext} disabled={end >= total}>
          Next page
        </Button>
      </div>
    </nav>
  )
}
