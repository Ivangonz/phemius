import { useTodayStats, type TodayStats } from "@/hooks/useTodayStats"
import { formatCost } from "@/lib/formatCost"

function describeStats(stats: TodayStats) {
  const cost = stats.estimated_cost_usd
  return [
    { label: "Scripts written", value: String(stats.scripts_written) },
    { label: "Audio files made", value: String(stats.audio_files) },
    { label: "Narration", value: `${Math.round(stats.narration_minutes)} min` },
    {
      label: "Estimated model cost",
      value: cost === null ? "Not priced" : formatCost(cost),
    },
  ]
}

function describeUnpriced(count: number): string | null {
  if (count === 0) return null
  const scripts = count === 1 ? "1 script has" : `${count} scripts have`
  return `${scripts} no price, so the estimate leaves them out.`
}

export function TodayPanel() {
  const { data: stats, isError } = useTodayStats()
  const unpriced = stats ? describeUnpriced(stats.unpriced_scripts) : null

  return (
    <aside
      aria-label="Today"
      className="flex min-w-0 flex-[1_1_280px] flex-col gap-4 rounded-panel border border-line bg-surface p-5"
    >
      <h2 className="text-base font-semibold">Today</h2>
      {isError && <p role="alert">Today's totals could not be loaded.</p>}
      {stats && (
        <dl className="flex flex-col gap-3">
          {describeStats(stats).map(({ label, value }) => (
            <div
              key={label}
              className="flex items-baseline justify-between gap-3 border-b border-line pb-3"
            >
              <dt className="text-muted">{label}</dt>
              <dd className="font-mono text-xl font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="text-small leading-relaxed text-muted">
        {unpriced} Cost is an estimate from the model price at the time of each
        run. Local voices cost nothing.
      </p>
    </aside>
  )
}
