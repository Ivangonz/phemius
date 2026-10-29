import { Link } from "@tanstack/react-router"
import { useSetupChecks } from "@/hooks/useSetupChecks"
import { attentionPath, needingAttention } from "@/lib/setupChecks"

export function SidebarCheckWarning() {
  const { data } = useSetupChecks()
  const problems = needingAttention(data?.checks ?? [])
  if (problems.length === 0) return null

  const count = problems.length
  const label =
    count === 1 ? "1 check needs attention" : `${count} checks need attention`

  return (
    <Link
      to={attentionPath(problems)}
      className="-mx-1 inline-flex min-h-11 items-center gap-2 rounded-nav px-1 text-small font-medium text-sidebar-value underline-offset-2 hover:underline"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="shrink-0 text-warning"
      >
        <path d="M12 3.5L2.5 20h19L12 3.5z" />
        <path d="M12 10v4.5M12 17.5v.5" />
      </svg>
      {label}
    </Link>
  )
}
