import { SidebarNavLink } from "./SidebarNavLink"
import { SidebarStatusCard } from "./SidebarStatusCard"

export function SidebarFooter() {
  return (
    <div className="flex flex-col gap-3 md:mt-auto">
      <SidebarStatusCard />
      <ul>
        <SidebarNavLink to="/settings" label="Settings" icon="settings" />
      </ul>
    </div>
  )
}
