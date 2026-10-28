import { SidebarNavLink } from "./SidebarNavLink"

// C3: the status card fills in once the settings API reports the script model,
// voice and library counts.
export function SidebarFooter() {
  return (
    <div className="flex flex-col gap-3 md:mt-auto">
      <div className="hidden flex-col gap-2.5 rounded-control bg-sidebar-card px-3 py-3.5 md:flex">
        <div className="text-label text-sidebar-label uppercase">
          Script model and voice
        </div>
        <div className="font-mono text-small text-sidebar-value">
          Configured in Settings
        </div>
      </div>
      <ul>
        <SidebarNavLink to="/settings" label="Settings" icon="settings" />
      </ul>
    </div>
  )
}
