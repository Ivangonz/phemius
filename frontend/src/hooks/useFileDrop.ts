import { useRef, useState, type DragEvent } from "react"

function carriesFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer.types).includes("Files")
}

export function useFileDrop(onFiles: (files: File[]) => void) {
  const [isDragging, setIsDragging] = useState(false)
  // dragenter and dragleave fire for every child element crossed.
  const depth = useRef(0)

  function handleDragEnter(event: DragEvent) {
    if (!carriesFiles(event)) return
    event.preventDefault()
    depth.current += 1
    setIsDragging(true)
  }

  function handleDragOver(event: DragEvent) {
    if (!carriesFiles(event)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = "copy"
  }

  function handleDragLeave(event: DragEvent) {
    if (!carriesFiles(event)) return
    depth.current = Math.max(0, depth.current - 1)
    if (depth.current === 0) setIsDragging(false)
  }

  function handleDrop(event: DragEvent) {
    if (!carriesFiles(event)) return
    event.preventDefault()
    depth.current = 0
    setIsDragging(false)
    const files = Array.from(event.dataTransfer.files)
    if (files.length > 0) onFiles(files)
  }

  return {
    isDragging,
    dropHandlers: {
      onDragEnter: handleDragEnter,
      onDragOver: handleDragOver,
      onDragLeave: handleDragLeave,
      onDrop: handleDrop,
    },
  }
}
