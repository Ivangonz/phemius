import { useId } from "react"
import { Button } from "@/components/ui/Button"

type DeleteSourceConfirmProps = {
  name: string
  isDeleting: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function DeleteSourceConfirm({
  name,
  isDeleting,
  onConfirm,
  onCancel,
}: DeleteSourceConfirmProps) {
  const titleId = useId()

  return (
    <div
      role="group"
      aria-labelledby={titleId}
      className="flex w-full flex-col gap-3 rounded-control border border-danger-line bg-surface-subtle p-3.5"
    >
      <p id={titleId} className="text-secondary leading-relaxed">
        <strong className="font-semibold">Delete {name}?</strong> Phemius stops
        watching it and forgets its activity. Documents already imported stay in
        the library.
      </p>
      <div className="flex flex-wrap gap-2.5">
        <Button onClick={onConfirm} disabled={isDeleting}>
          {isDeleting ? "Deleting…" : "Delete source"}
        </Button>
        {/* Focus the safe choice, so Enter cannot delete by accident. */}
        <Button autoFocus variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
