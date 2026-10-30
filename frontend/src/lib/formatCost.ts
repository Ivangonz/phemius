// Local runs cost fractions of a cent, so small amounts keep a third decimal
// instead of rounding to $0.00.
export function formatCost(usd: number): string {
  if (!Number.isFinite(usd) || usd <= 0) return "$0.00"
  return `$${usd.toFixed(usd < 0.01 ? 3 : 2)}`
}
