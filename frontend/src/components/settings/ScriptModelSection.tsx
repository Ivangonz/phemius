import { Button } from "@/components/ui/Button"
import { useSettings } from "@/hooks/useSettings"
import { ApiError, getErrorMessage } from "@/lib/api"
import { ScriptModelForm } from "./ScriptModelForm"

export function ScriptModelSection() {
  const settings = useSettings()

  return (
    <section
      aria-labelledby="script-model-heading"
      className="flex min-w-0 flex-col gap-4.5 rounded-panel border border-line bg-surface p-5.5"
    >
      <div>
        <h2 id="script-model-heading" className="text-lg font-semibold">
          Script model
        </h2>
        <p className="mt-1 text-secondary text-muted">
          Categorizes documents and rewrites them so they sound right read
          aloud.
        </p>
      </div>
      {settings.isPending && <p className="text-muted">Loading settings…</p>}
      {settings.isError && (
        <div role="alert" className="flex flex-col items-start gap-2">
          <p className="font-semibold text-danger-ink">
            Settings could not be loaded: {getErrorMessage(settings.error)}
          </p>
          {settings.error instanceof ApiError && settings.error.hint && (
            <p className="text-muted">{settings.error.hint}</p>
          )}
          <Button variant="secondary" onClick={() => void settings.refetch()}>
            Try again
          </Button>
        </div>
      )}
      {settings.data && <ScriptModelForm overview={settings.data} />}
    </section>
  )
}
