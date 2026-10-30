import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { isJobActive } from "@/lib/documentStatus"
import { documentsQueryKey } from "./useDocuments"

export type DocumentDetail = components["schemas"]["Document"]
type VersionPage = components["schemas"]["Page_VersionSummary_"]

const ACTIVE_POLL_MS = 2_000

export function documentQueryKey(documentId: number) {
  return [...documentsQueryKey, "detail", documentId] as const
}

function hasActiveAudio(page: VersionPage | undefined): boolean {
  return Boolean(page?.items.some((version) => version.audio.some(isJobActive)))
}

export function useDocument(documentId: number) {
  return useQuery({
    queryKey: documentQueryKey(documentId),
    queryFn: () => api.get<DocumentDetail>(`/docs/${documentId}`),
  })
}

export function useDocumentVersions(documentId: number) {
  return useQuery({
    queryKey: [...documentQueryKey(documentId), "versions"],
    queryFn: () => api.get<VersionPage>(`/docs/${documentId}/versions`),
    refetchInterval: (current) =>
      hasActiveAudio(current.state.data) ? ACTIVE_POLL_MS : false,
  })
}
