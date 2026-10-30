import { useId } from "react"
import { useFormContext, type FieldValues, type Path } from "react-hook-form"
import type { ProviderOption } from "@/lib/settingsFields"
import { ProviderCard } from "./ProviderCard"

type ProviderCardsProps<T extends FieldValues> = {
  name: NoInfer<Path<T>>
  legend: string
  options: ProviderOption[]
  isLocked: boolean
  lockedNote: string
}

// T defaults to never so a caller must name its form type.
export function ProviderCards<T extends FieldValues = never>({
  name,
  legend,
  options,
  isLocked,
  lockedNote,
}: ProviderCardsProps<T>) {
  const lockedId = useId()
  const { register } = useFormContext<T>()
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
