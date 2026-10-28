import type { ReactNode } from "react"

export type NavIconName = "library" | "sources" | "queue" | "settings"

const ICON_SHAPES: Record<NavIconName, ReactNode> = {
  library: <path d="M4 5h4v14H4zM10 5h4v14h-4zM16.5 6.5l3.5-1 3 12.5-3.5 1z" />,
  sources: (
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  ),
  queue: (
    <>
      <path d="M4 6h12M4 12h8M4 18h6" />
      <circle cx="18" cy="16" r="4" />
      <path d="M18 14v2l1.2 1" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </>
  ),
}

export function NavIcon({ name }: { name: NavIconName }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0"
    >
      {ICON_SHAPES[name]}
    </svg>
  )
}
