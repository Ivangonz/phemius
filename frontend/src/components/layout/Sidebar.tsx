import { useId, useState } from "react"
import { useRouterState } from "@tanstack/react-router"
import { LogoMark } from "./LogoMark"
import { MenuButton } from "./MenuButton"
import { SidebarFooter } from "./SidebarFooter"
import { SidebarNavLink } from "./SidebarNavLink"

export function Sidebar() {
  const menuId = useId()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const [menuOpenedAt, setMenuOpenedAt] = useState<string | null>(null)
  // The phone menu belongs to the page it was opened on, so navigating closes it.
  const isMenuOpen = menuOpenedAt === pathname

  function handleMenuToggle() {
    setMenuOpenedAt(isMenuOpen ? null : pathname)
  }

  return (
    <nav
      aria-label="Main"
      className="flex flex-col gap-3 bg-sidebar px-3.5 py-2 text-sidebar-ink md:sticky md:top-0 md:h-screen md:w-58 md:shrink-0 md:gap-7 md:py-5.5"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 px-2">
          <LogoMark />
          <span className="text-wordmark font-semibold text-white">
            Phemius
          </span>
        </div>
        <MenuButton
          isOpen={isMenuOpen}
          controls={menuId}
          onClick={handleMenuToggle}
        />
      </div>
      <div
        id={menuId}
        className={`${isMenuOpen ? "flex" : "hidden"} flex-1 flex-col gap-3 pb-2 md:flex md:gap-7 md:pb-0`}
      >
        <ul className="flex flex-col gap-1">
          <SidebarNavLink to="/" label="Library" icon="library" />
          <SidebarNavLink to="/sources" label="Sources" icon="sources" />
          <SidebarNavLink to="/queue" label="Queue" icon="queue" />
        </ul>
        <SidebarFooter />
      </div>
    </nav>
  )
}
