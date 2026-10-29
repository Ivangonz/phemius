import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { setAccessToken } from "@/lib/accessToken"
import { api } from "@/lib/api"
import type { components } from "@/lib/api-schema"

export type AccessStatus = components["schemas"]["AccessStatus"]
export type AccessMode = components["schemas"]["AccessMode"]
type AccessToken = components["schemas"]["AccessToken"]

export const accessQueryKey = ["access"] as const

export function useAccessStatus() {
  return useQuery({
    queryKey: accessQueryKey,
    queryFn: () => api.get<AccessStatus>("/access"),
  })
}

export function useRegenerateToken() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const { token } = await api.post<AccessToken>("/access/token")
      // Saved before anything refetches, so this browser keeps working.
      setAccessToken(token)
      return token
    },
    // The token is shown once: do not keep it in the mutation cache.
    gcTime: 0,
    // Every query (and signed audio link) was made with the old token.
    onSuccess: () => queryClient.invalidateQueries(),
  })
}
