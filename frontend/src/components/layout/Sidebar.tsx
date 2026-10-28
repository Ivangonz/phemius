import { LogoMark } from "./LogoMark"
import { SidebarFooter } from "./SidebarFooter"
import { SidebarNavLink } from "./SidebarNavLink"

export function Sidebar() {
  return (
    <nav
      aria-label="Main"
      className="flex flex-wrap items-center gap-x-4 gap-y-3 bg-sidebar px-3.5 py-4 text-sidebar-ink md:sticky md:top-0 md:h-screen md:w-58 md:shrink-0 md:flex-col md:flex-nowrap md:items-stretch md:gap-7 md:py-5.5"
    >
      <div className="flex items-center gap-2.5 px-2">
        <LogoMark />
        <span className="text-wordmark font-semibold text-white">Phemius</span>
      </div>
      <ul className="flex flex-wrap gap-1 md:flex-col">
        <SidebarNavLink to="/" label="Library" icon="library" />
        <SidebarNavLink to="/sources" label="Sources" icon="sources" />
        <SidebarNavLink to="/queue" label="Queue" icon="queue" />
      </ul>
      <SidebarFooter />
    </nav>
  )
}
