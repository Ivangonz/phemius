import { useCallback, useRef, useState } from "react"
import {
  describeUploadError,
  describeUploadResult,
  UPLOADING,
  WAITING,
  type UploadOutcome,
} from "@/lib/uploadOutcome"
import { useUploadDocument } from "./useUploadDocument"

export type UploadEntry = {
  id: number
  name: string
  outcome: UploadOutcome
}

// Files go up one request at a time so each gets its own result, and the
// server imports them one after another instead of all at once.
export function useUploadQueue() {
  const { mutateAsync: uploadDocument } = useUploadDocument()
  const [entries, setEntries] = useState<UploadEntry[]>([])
  const nextId = useRef(0)
  const queue = useRef(Promise.resolve())

  const setOutcome = useCallback((id: number, outcome: UploadOutcome) => {
    setEntries((current) =>
      current.map((entry) => (entry.id === id ? { ...entry, outcome } : entry)),
    )
  }, [])

  const uploadOne = useCallback(
    async (id: number, file: File) => {
      setOutcome(id, UPLOADING)
      try {
        setOutcome(id, describeUploadResult(await uploadDocument(file)))
      } catch (error) {
        setOutcome(id, describeUploadError(error))
      }
    },
    [setOutcome, uploadDocument],
  )

  const addFiles = useCallback(
    (files: File[]) => {
      const added = files.map((file) => ({
        file,
        entry: { id: nextId.current++, name: file.name, outcome: WAITING },
      }))
      setEntries((current) => [...current, ...added.map(({ entry }) => entry)])
      for (const { file, entry } of added) {
        queue.current = queue.current.then(() => uploadOne(entry.id, file))
      }
    },
    [uploadOne],
  )

  const clearFinished = useCallback(() => {
    setEntries((current) =>
      current.filter((entry) => !entry.outcome.isFinished),
    )
  }, [])

  return { entries, addFiles, clearFinished }
}
