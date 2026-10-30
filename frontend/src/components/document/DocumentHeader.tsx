import { Link } from "@tanstack/react-router"
import { SuitabilityBadge } from "@/components/library/SuitabilityBadge"
import type { DocumentDetail } from "@/hooks/useDocument"
import { formatDate } from "@/lib/audioVersions"

export function DocumentHeader({ document }: { document: DocumentDetail }) {
  return (
    <header className="flex flex-col gap-2.5">
      <nav aria-label="Breadcrumb" className="text-secondary text-muted">
        <Link
          to="/"
          className="rounded-sm text-primary hover:text-primary-hover hover:underline"
        >
          Library
        </Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{document.title}</span>
      </nav>
      <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.01em] break-words">
        {document.title}
      </h1>
      <div className="flex flex-wrap items-center gap-2 text-small">
        <span className="rounded-pill bg-chip px-2 py-0.5 font-medium text-chip-ink">
          <span className="sr-only">Category: </span>
          {document.category}
        </span>
        <SuitabilityBadge
          suitability={document.audio_suitability}
          isAlwaysShown
        />
        <span className="font-mono break-all text-muted">
          {document.source} · updated {formatDate(document.created)}
        </span>
      </div>
      <p className="max-w-prose">{document.summary}</p>
      {document.suitability_reason && (
        <p className="max-w-prose text-secondary text-muted">
          {document.suitability_reason}
        </p>
      )}
    </header>
  )
}
