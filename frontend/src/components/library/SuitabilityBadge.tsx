import type { components } from "@/lib/api-schema"

type AudioSuitability = components["schemas"]["AudioSuitability"]

const LABELS: Record<AudioSuitability, string> = {
  recommended: "Great for audio",
  partial: "Partly suited to audio",
  not_recommended: "Not suited to audio",
}

const WARNING_CLASSES = "bg-warning text-warning-ink"
const GOOD_CLASSES = "bg-success text-success-ink"

type SuitabilityBadgeProps = {
  suitability: AudioSuitability | null
  isAlwaysShown?: boolean
}

export function SuitabilityBadge({
  suitability,
  isAlwaysShown = false,
}: SuitabilityBadgeProps) {
  if (!suitability) return null
  const isRecommended = suitability === "recommended"
  if (isRecommended && !isAlwaysShown) return null

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill px-2 py-0.5 font-medium ${isRecommended ? GOOD_CLASSES : WARNING_CLASSES}`}
    >
      {!isRecommended && <span aria-hidden="true">!</span>}
      {LABELS[suitability]}
    </span>
  )
}
