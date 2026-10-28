import { useRef, type ChangeEvent } from "react"
import { Button } from "@/components/ui/Button"

export function UploadButton({
  onFiles,
}: {
  onFiles: (files: File[]) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    // Clearing lets the same file be chosen again after a failed upload.
    event.target.value = ""
    if (files.length > 0) onFiles(files)
  }

  return (
    <>
      <Button onClick={() => inputRef.current?.click()}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M12 16V4M7 9l5-5 5 5M5 20h14" />
        </svg>
        Upload documents
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        aria-label="Choose documents to upload"
        onChange={handleChange}
      />
    </>
  )
}
