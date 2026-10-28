import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"

export type LibraryConfig = components["schemas"]["LibraryConfig"]

export const libraryConfigQueryKey = ["config"] as const

export function useLibraryConfig() {
  return useQuery({
    queryKey: libraryConfigQueryKey,
    queryFn: () => api.get<LibraryConfig>("/config"),
  })
}
