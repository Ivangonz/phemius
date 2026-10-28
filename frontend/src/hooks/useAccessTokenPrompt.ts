import { useCallback, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { setAccessToken } from "@/lib/accessToken"
import { setUnauthorizedHandler } from "@/lib/api"

export function useAccessTokenPrompt() {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    setUnauthorizedHandler(() => setIsOpen(true))
    return () => setUnauthorizedHandler(null)
  }, [])

  const saveToken = useCallback(
    (token: string) => {
      setAccessToken(token)
      setIsOpen(false)
      // Every query may have failed with the old token, so refetch them all.
      void queryClient.invalidateQueries()
    },
    [queryClient],
  )

  const close = useCallback(() => setIsOpen(false), [])

  return { isOpen, saveToken, close }
}
