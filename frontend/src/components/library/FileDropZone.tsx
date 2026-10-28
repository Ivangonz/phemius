import type { ReactNode } from "react"
import { useFileDrop } from "@/hooks/useFileDrop"

type FileDropZoneProps = {
  onFiles: (files: File[]) => void
  children: ReactNode
}

export function FileDropZone({ onFiles, children }: FileDropZoneProps) {
  const { isDragging, dropHandlers } = useFileDrop(onFiles)

  return (
    <div className="relative flex flex-1 flex-col gap-5" {...dropHandlers}>
      {children}
      {isDragging && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-panel border-2 border-dashed border-primary bg-primary-tint/90">
          <p className="text-lg font-semibold text-primary-tint-ink">
            Drop files to add them to your library
          </p>
        </div>
      )}
    </div>
  )
}
