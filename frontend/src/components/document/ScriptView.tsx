import { useId } from "react"
import { isJobActive } from "@/lib/documentStatus"
import type { AudioVersion } from "@/lib/audioVersions"

type ScriptViewProps = {
  script: string | null
  version: AudioVersion
}

function describeMissingScript(version: AudioVersion): string {
  if (isJobActive(version)) return "The script is still being written."
  return "This version has no script."
}

export function ScriptView({ script, version }: ScriptViewProps) {
  const headingId = useId()
  const paragraphs = script?.split(/\n\s*\n/).filter(Boolean) ?? []

  return (
    <section aria-labelledby={headingId} className="min-w-0">
      <h2
        id={headingId}
        className="mb-2 text-secondary font-semibold tracking-[0.05em] text-muted uppercase"
      >
        Spoken script
      </h2>
      <div className="flex flex-col gap-3 rounded-control border border-line bg-surface-subtle px-4.5 py-4 text-[15px] leading-[1.7]">
        {paragraphs.length > 0 ? (
          paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)
        ) : (
          <p className="text-muted">{describeMissingScript(version)}</p>
        )}
      </div>
    </section>
  )
}
