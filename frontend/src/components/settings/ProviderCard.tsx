import type { UseFormRegisterReturn } from "react-hook-form"
import type { ProviderOption, ProviderTag } from "@/lib/settingsFields"

const TAG_CLASSES: Record<ProviderTag, string> = {
  Cloud: "bg-chip text-chip-ink",
  "Your server": "bg-primary-tint text-primary-hover",
  Local: "bg-success text-success-ink",
}

type ProviderCardProps = {
  provider: ProviderOption
  registration: UseFormRegisterReturn
  isDisabled: boolean
}

export function ProviderCard({
  provider,
  registration,
  isDisabled,
}: ProviderCardProps) {
  return (
    <label className="flex min-h-11 flex-[1_1_12.5rem] cursor-pointer items-start gap-2.5 rounded-control border border-line bg-surface p-3 has-checked:border-primary has-checked:bg-selected has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary has-disabled:cursor-not-allowed">
      <input
        type="radio"
        value={provider.id}
        disabled={isDisabled}
        className="mt-0.75 size-4.5 flex-none accent-primary"
        {...registration}
      />
      <span className="flex flex-col gap-0.75">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{provider.label}</span>
          <span
            className={`rounded-pill px-2 py-0.5 text-label font-semibold ${TAG_CLASSES[provider.tag]}`}
          >
            {provider.tag}
          </span>
        </span>
        <span className="text-secondary leading-snug text-muted">
          {provider.description}
        </span>
      </span>
    </label>
  )
}
