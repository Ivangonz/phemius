import { Link, type LinkProps } from "@tanstack/react-router"

type Tab = { to: LinkProps["to"]; label: string }

const TABS: Tab[] = [
  { to: "/settings", label: "Models and voices" },
  { to: "/settings/server", label: "Server and self-hosting" },
]

const ACTIVE_PROPS = { className: "border-primary font-semibold text-ink" }
const INACTIVE_PROPS = {
  className: "border-transparent font-medium text-muted hover:text-ink",
}

export function SettingsTabs() {
  return (
    <nav
      aria-label="Settings sections"
      className="flex flex-wrap gap-1.5 border-b border-line"
    >
      {TABS.map((tab) => (
        <Link
          key={tab.label}
          to={tab.to}
          activeOptions={{ exact: true }}
          className="inline-flex min-h-11 items-center border-b-3 px-3.5"
          activeProps={ACTIVE_PROPS}
          inactiveProps={INACTIVE_PROPS}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  )
}
