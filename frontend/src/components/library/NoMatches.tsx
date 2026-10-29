import { Button } from "@/components/ui/Button"

export function NoMatches({ onClear }: { onClear: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-panel border border-line bg-surface px-6 py-10 text-center">
      <p className="text-muted">No documents match these filters.</p>
      <Button variant="secondary" onClick={onClear}>
        Clear filters
      </Button>
    </div>
  )
}
