const UNITS = ["KB", "MB", "GB"]

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 1000)
    return `${Math.max(0, bytes || 0)} B`
  let value = bytes
  let unit = ""
  for (const next of UNITS) {
    value /= 1000
    unit = next
    if (value < 1000) break
  }
  return `${value.toFixed(1)} ${unit}`
}
