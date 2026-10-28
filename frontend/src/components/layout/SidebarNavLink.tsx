import { Link, type LinkProps } from "@tanstack/react-router"
import { NavIcon, type NavIconName } from "./NavIcon"

type SidebarNavLinkProps = {
  to: LinkProps["to"]
  label: string
  icon: NavIconName
}

const ACTIVE_PROPS = { className: "bg-sidebar-active text-white" }
const INACTIVE_PROPS = {
  className: "text-sidebar-ink hover:bg-sidebar-active/60 hover:text-white",
}

export function SidebarNavLink({ to, label, icon }: SidebarNavLinkProps) {
  return (
    <li>
      <Link
        to={to}
        activeOptions={{ exact: to === "/" }}
        className="flex min-h-11 items-center gap-3 rounded-nav px-3 font-medium transition-colors focus-visible:outline-sidebar-value"
        activeProps={ACTIVE_PROPS}
        inactiveProps={INACTIVE_PROPS}
      >
        <NavIcon name={icon} />
        {label}
      </Link>
    </li>
  )
}
