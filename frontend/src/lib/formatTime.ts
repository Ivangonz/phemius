export function formatTime(totalSeconds: number): string {
  const seconds = Number.isFinite(totalSeconds)
    ? Math.max(0, Math.floor(totalSeconds))
    : 0
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secondsPart = String(seconds % 60).padStart(2, "0")
  if (hours === 0) return `${minutes}:${secondsPart}`
  return `${hours}:${String(minutes).padStart(2, "0")}:${secondsPart}`
}
