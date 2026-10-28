import type { ReactNode } from "react"
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query"
import { PlayerProvider } from "./player/PlayerProvider"

type AppProvidersProps = {
  queryClient: QueryClient
  children: ReactNode
}

// The player sits above the router so navigating never unmounts the audio.
export function AppProviders({ queryClient, children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <PlayerProvider>{children}</PlayerProvider>
    </QueryClientProvider>
  )
}
