import { useId } from "react"
import { useFormContext } from "react-hook-form"
import type { ProviderOption } from "@/lib/scriptModelSettings"
import { ProviderCard } from "./ProviderCard"

type ProviderCardsProps = {
  name: string
  legend: string
  options: ProviderOption[]
  isLocked: boolean
  lockedNote: string
}

export function ProviderCards({
  name,
  legend,
  options,
  isLocked,
  lockedNote,
}: ProviderCardsProps) {
  const lockedId = useId()
  const { register } = useFormContext()
  const registration = register(name)

  return (
    <fieldset
      className="flex flex-col gap-2"
      aria-describedby={isLocked ? lockedId : undefined}
    >
      <legend className="mb-2 text-secondary font-semibold">{legend}</legend>
      {isLocked && (
        <p id={lockedId} className="text-secondary text-muted">
          {lockedNote}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <ProviderCard
            key={option.id}
            provider={option}
            registration={registration}
            isDisabled={isLocked}
          />
        ))}
      </div>
    </fieldset>
  )
}
