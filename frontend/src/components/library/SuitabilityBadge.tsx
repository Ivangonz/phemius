import type { components } from "@/lib/api-schema"

type AudioSuitability = components["schemas"]["AudioSuitability"]

const LABELS: Partial<Record<AudioSuitability, string>> = {
  partial: "Partly suited to audio",
  not_recommended: "Not suited to audio",
}

export function SuitabilityBadge({
  suitability,
}: {
  suitability: AudioSuitability | null
}) {
  const label = suitability ? LABELS[suitability] : undefined
  if (!label) return null

  return (
    <span className="inline-flex items-center gap-1 rounded-pill bg-warning px-2 py-0.5 font-medium text-warning-ink">
      <span aria-hidden="true">!</span>
      {label}
    </span>
  )
}
