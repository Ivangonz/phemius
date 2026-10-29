import { useId } from "react"

export type FilterOption = { value: string; label: string }

type FilterSelectProps = {
  label: string
  value: string
  options: FilterOption[]
  onChange: (value: string) => void
}

export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: FilterSelectProps) {
  const id = useId()

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-small font-medium text-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 min-w-0 cursor-pointer rounded-control border border-line-control bg-surface px-3"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
