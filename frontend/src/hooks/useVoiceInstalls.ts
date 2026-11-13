import { useEffect, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { libraryConfigQueryKey } from "./useLibraryConfig"
import { voicesQueryKey } from "./useSettings"
import { voicePath, type VoiceView } from "./useVoices"

type DownloadProgress = components["schemas"]["DownloadProgress"]
export type InstallNote = {
  voiceId: string
  kind: "started" | "installed" | "failed"
}
type StartErrors = Readonly<Record<string, Error>>

function withId(ids: ReadonlySet<string>, id: string): ReadonlySet<string> {
  return new Set(ids).add(id)
}

function withoutIds(ids: ReadonlySet<string>, gone: string[]) {
  return new Set([...ids].filter((id) => !gone.includes(id)))
}

function withoutErrors(errors: StartErrors, gone: string[]): StartErrors {
  return Object.fromEntries(
    Object.entries(errors).filter(([id]) => !gone.includes(id)),
  )
}

function isUnderway(voice: VoiceView): boolean {
  return voice.is_installed || voice.download?.state === "downloading"
}

function finishedKind(voice: VoiceView): InstallNote["kind"] | null {
  if (voice.is_installed) return "installed"
  return voice.download?.state === "failed" ? "failed" : null
}

// TanStack tracks only a mutation's latest call, so starts and their errors
// are kept per voice. Started voices are watched until the polled list shows
// them installed or failed, which is announced once.
export function useVoiceInstalls(items: VoiceView[]) {
  const queryClient = useQueryClient()
  const [starting, setStarting] = useState<ReadonlySet<string>>(new Set())
  const [watching, setWatching] = useState<ReadonlySet<string>>(new Set())
  const [startErrors, setStartErrors] = useState<StartErrors>({})
  const [note, setNote] = useState<InstallNote | null>(null)
  const [seenItems, setSeenItems] = useState(items)

  if (seenItems !== items) {
    setSeenItems(items)
    const finished = items.filter(
      (voice) => watching.has(voice.id) && finishedKind(voice),
    )
    const lastFinished = finished.at(-1)
    if (lastFinished) {
      setWatching(
        withoutIds(
          watching,
          finished.map((voice) => voice.id),
        ),
      )
      const kind = finishedKind(lastFinished) ?? "failed"
      setNote({ voiceId: lastFinished.id, kind })
    }
    const stale = items
      .filter((voice) => startErrors[voice.id] && isUnderway(voice))
      .map((voice) => voice.id)
    if (stale.length) setStartErrors(withoutErrors(startErrors, stale))
  }

  useEffect(() => {
    if (note?.kind === "installed")
      void queryClient.invalidateQueries({ queryKey: libraryConfigQueryKey })
  }, [note, queryClient])

  const download = useMutation({
    mutationFn: (voiceId: string) =>
      api.post<DownloadProgress>(`${voicePath(voiceId)}/download`),
    onMutate: (voiceId) => {
      setStarting((ids) => withId(ids, voiceId))
      setStartErrors((errors) => withoutErrors(errors, [voiceId]))
    },
    onSuccess: (_progress, voiceId) => {
      setWatching((ids) => withId(ids, voiceId))
      setNote({ voiceId, kind: "started" })
    },
    onError: (error, voiceId) =>
      setStartErrors((errors) => ({ ...errors, [voiceId]: error })),
    onSettled: (_progress, _error, voiceId) => {
      setStarting((ids) => withoutIds(ids, [voiceId]))
      return queryClient.invalidateQueries({ queryKey: voicesQueryKey })
    },
  })

  const busyId =
    items.find((voice) => voice.download?.state === "downloading")?.id ??
    [...starting][0] ??
    null

  return {
    install: download.mutate,
    isStarting: (voiceId: string) => starting.has(voiceId),
    startError: (voiceId: string) => startErrors[voiceId] ?? null,
    busyId,
    note,
  }
}
