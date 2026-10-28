import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { AppShell } from "@/components/layout/AppShell"
import { NotFound } from "@/components/NotFound"
import { RouteError } from "@/components/RouteError"
import { TokenPrompt } from "@/components/TokenPrompt"
import { useAccessTokenPrompt } from "@/hooks/useAccessTokenPrompt"

export type RouterContext = {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  errorComponent: RouteError,
  notFoundComponent: NotFound,
})

function RootLayout() {
  const tokenPrompt = useAccessTokenPrompt()

  return (
    <>
      <AppShell>
        <Outlet />
      </AppShell>
      {tokenPrompt.isOpen && (
        <TokenPrompt
          onSave={tokenPrompt.saveToken}
          onClose={tokenPrompt.close}
        />
      )}
    </>
  )
}
