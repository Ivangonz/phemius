import type { components } from "./api-schema"
import { formatBytes } from "./formatBytes"

type DownloadProgress = components["schemas"]["DownloadProgress"]

export function downloadProgressText(download: DownloadProgress): string {
  const done = download.done ?? 0
  const total = download.total
  if (!total) return `Downloading… ${formatBytes(done)}`
  const percent = Math.min(100, Math.round((done / total) * 100))
  return `Downloading… ${formatBytes(done)} of ${formatBytes(total)} (${percent}%)`
}
