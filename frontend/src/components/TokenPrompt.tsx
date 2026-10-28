import { useEffect, useId, useRef, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/Button"

type TokenPromptProps = {
  onSave: (token: string) => void
  onClose: () => void
}

export function TokenPrompt({ onSave, onClose }: TokenPromptProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [token, setToken] = useState("")
  const titleId = useId()
  const inputId = useId()
  const trimmedToken = token.trim()

  useEffect(() => {
    dialogRef.current?.showModal()
  }, [])

  // Closing through the dialog (not by unmounting) returns focus to where it was.
  function handleCancel() {
    dialogRef.current?.close()
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmedToken) return
    onSave(trimmedToken)
    dialogRef.current?.close()
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      className="m-auto w-[min(100%-2rem,26rem)] rounded-panel border border-line bg-surface p-6 text-ink backdrop:bg-ink/50"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <h2 id={titleId} className="text-lg font-semibold">
            Access token required
          </h2>
          <p className="mt-1 text-muted">
            This Phemius server needs its access token. It is saved in this
            browser only.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={inputId} className="font-medium">
            Access token
          </label>
          <input
            id={inputId}
            type="password"
            autoComplete="off"
            required
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="min-h-11 rounded-control border border-line-control bg-surface px-3 font-mono"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-2.5">
          <Button variant="secondary" onClick={handleCancel}>
            Cancel
          </Button>
          <Button type="submit">Save token</Button>
        </div>
      </form>
    </dialog>
  )
}
