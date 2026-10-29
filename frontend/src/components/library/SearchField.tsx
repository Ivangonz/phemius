import { useEffect, useId, useState } from "react"

const SEARCH_DELAY_MS = 300

type SearchFieldProps = {
  value: string
  onSearch: (value: string) => void
}

export function SearchField({ value, onSearch }: SearchFieldProps) {
  const id = useId()
  const [text, setText] = useState(value)
  const [committed, setCommitted] = useState(value)

  // Follow outside changes (clearing filters, the back button) without
  // remounting the input, which would drop focus mid-typing.
  if (value !== committed) {
    setCommitted(value)
    setText(value)
  }

  useEffect(() => {
    if (text === committed) return
    const timer = setTimeout(() => onSearch(text), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [text, committed, onSearch])

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-small font-medium text-muted">
        Search titles
      </label>
      <input
        id={id}
        type="search"
        value={text}
        placeholder="Search titles"
        onChange={(event) => setText(event.target.value)}
        className="min-h-11 min-w-0 rounded-control border border-line-control bg-surface px-3"
      />
    </div>
  )
}
