import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { documentsQueryKey } from "./useDocuments"
import { queueQueryKey } from "./useQueue"

type AudioRequest = components["schemas"]["AudioRequest"]
type AudioCreated = components["schemas"]["AudioCreated"]

export function useGenerateVersion(documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: AudioRequest) =>
      api.post<AudioCreated>(`/docs/${documentId}/audio`, request),
    onSuccess: () =>
      Promise.all(
        [documentsQueryKey, queueQueryKey].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}
