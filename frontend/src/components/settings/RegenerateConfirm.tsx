import { useId } from "react"
import { Button } from "@/components/ui/Button"

type RegenerateConfirmProps = {
  onConfirm: () => void
  onCancel: () => void
}

export function RegenerateConfirm({
  onConfirm,
  onCancel,
}: RegenerateConfirmProps) {
  const titleId = useId()

  return (
    <div
      role="group"
      aria-labelledby={titleId}
      className="mt-1 flex flex-col gap-3 rounded-control border border-danger-line bg-surface-subtle p-3.5"
    >
      <p id={titleId} className="text-secondary leading-relaxed">
        <strong className="font-semibold">Regenerate the access token?</strong>{" "}
        The current token stops working at once. Other devices must enter the
        new one, and audio links already open stop playing until they reload.
      </p>
      <div className="flex flex-wrap gap-2.5">
        <Button onClick={onConfirm}>Regenerate token</Button>
        {/* Focus the safe choice, so Enter cannot replace the token by accident. */}
        <Button autoFocus variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
