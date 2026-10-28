import { createRouter, type RouterHistory } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { routeTree } from "@/routeTree.gen"

export function createAppRouter(
  queryClient: QueryClient,
  history?: RouterHistory,
) {
  return createRouter({
    routeTree,
    history,
    context: { queryClient },
    defaultPreload: "intent",
  })
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
