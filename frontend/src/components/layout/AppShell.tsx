import type { ReactNode } from "react"
import { Sidebar } from "./Sidebar"

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col gap-5 px-5 py-6 md:px-8 md:py-7">
        {children}
      </main>
    </div>
  )
}
