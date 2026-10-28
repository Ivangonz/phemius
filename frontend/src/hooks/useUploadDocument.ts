import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { documentsQueryKey } from "./useDocuments"

export type UploadResult = components["schemas"]["UploadResult"]

export function useUploadDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (file: File): Promise<UploadResult> => {
      const body = new FormData()
      body.append("files", file)
      const [result] = await api.post<UploadResult[]>("/docs", body)
      return result ?? { file: file.name, error: "The server sent no result." }
    },
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: documentsQueryKey }),
  })
}
