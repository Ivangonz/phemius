import { useId } from "react"
import { useFormContext } from "react-hook-form"
import {
  PROVIDERS,
  type ScriptModelFormValues,
} from "@/lib/scriptModelSettings"
import { ProviderCard } from "./ProviderCard"

type ProviderCardsProps = { isLocked: boolean }

export function ProviderCards({ isLocked }: ProviderCardsProps) {
  const lockedId = useId()
  const { register } = useFormContext<ScriptModelFormValues>()
  const registration = register("script_provider")

  return (
    <fieldset
      className="flex flex-col gap-2"
      aria-describedby={isLocked ? lockedId : undefined}
    >
      <legend className="mb-2 text-secondary font-semibold">
        Where the model runs
      </legend>
      {isLocked && (
        <p id={lockedId} className="text-secondary text-muted">
          Locked: the provider is set by PHEMIUS_SCRIPT_PROVIDER on the server.
          Unset it and restart to choose here.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {PROVIDERS.map((provider) => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            registration={registration}
            isDisabled={isLocked}
          />
        ))}
      </div>
    </fieldset>
  )
}
