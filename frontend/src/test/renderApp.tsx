import type { ReactNode } from "react"
import { render } from "@testing-library/react"
import { QueryClient } from "@tanstack/react-query"
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router"
import { AppProviders } from "@/components/AppProviders"
import { createAppRouter } from "@/lib/router"

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function renderAppAt(path: string, outsideRouter?: ReactNode) {
  const queryClient = createTestQueryClient()
  const router = createAppRouter(
    queryClient,
    createMemoryHistory({ initialEntries: [path] }),
  )
  render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
      {outsideRouter}
    </AppProviders>,
  )
  return { router, queryClient }
}
