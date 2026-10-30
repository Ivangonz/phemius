import { Button } from "@/components/ui/Button"

type RuleOriginProps = {
  id: string
  label: string
  description: string
  isOwn: boolean
  onReset: () => void
}

export function RuleOrigin({
  id,
  label,
  description,
  isOwn,
  onReset,
}: RuleOriginProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-secondary text-muted">
      <p id={id}>{description}</p>
      {isOwn && (
        <Button variant="secondary" className="px-3" onClick={onReset}>
          Reset<span className="sr-only"> {label}</span>
        </Button>
      )}
    </div>
  )
}
