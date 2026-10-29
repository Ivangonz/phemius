import { useId, useRef, useState } from "react"
import { Button } from "@/components/ui/Button"

type CopyState = "idle" | "copied" | "failed"

const COPY_MESSAGES: Record<CopyState, string> = {
  idle: "",
  copied: "Copied",
  failed: "Could not copy. Select the token and copy it yourself.",
}

type NewTokenRevealProps = { token: string }

export function NewTokenReveal({ token }: NewTokenRevealProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [copyState, setCopyState] = useState<CopyState>("idle")
  const inputId = useId()

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(token)
      setCopyState("copied")
    } catch {
      inputRef.current?.select()
      setCopyState("failed")
    }
  }

  return (
    <div className="mt-1 flex flex-col gap-2 rounded-control border border-primary bg-selected p-3.5">
      <label htmlFor={inputId} className="text-secondary font-semibold">
        New access token
      </label>
      <div className="flex gap-2">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          readOnly
          value={token}
          onFocus={(event) => event.currentTarget.select()}
          className="min-h-11 min-w-0 flex-1 rounded-control border border-line-control bg-surface px-3 font-mono"
        />
        <Button variant="secondary" onClick={() => void handleCopy()}>
          Copy
        </Button>
      </div>
      <p role="status" className="text-small font-medium">
        {COPY_MESSAGES[copyState]}
      </p>
      <p className="text-secondary leading-relaxed">
        <strong className="font-semibold">Shown only now.</strong> This browser
        already uses it. Enter it on your other devices; audio links opened with
        the old token need a reload.
      </p>
    </div>
  )
}
