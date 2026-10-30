import type { components } from "./api-schema"
import type { StatusKind } from "./documentStatus"

type SourceView = components["schemas"]["SourceView"]

const KIND_LABELS: Record<string, string> = { folder: "Watched folder" }

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind
}

export function sourceStatus(
  source: SourceView,
  isSyncing: boolean,
): { label: string; kind: StatusKind } {
  if (source.status === "paused") return { label: "Paused", kind: "idle" }
  if (isSyncing) return { label: "Syncing", kind: "working" }
  if (source.error) return { label: "Error", kind: "failed" }
  return { label: "Watching", kind: "ready" }
}

export function folderPath(source: SourceView): string | null {
  const path = source.config.path
  return typeof path === "string" ? path : null
}

export function describeLastSync(lastSync: number | null): string {
  if (lastSync === null) return "Not synced yet"
  const when = new Date(lastSync * 1000).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
  return `Last sync ${when}`
}

export function describeFileTypes(source: SourceView): string {
  const types = source.effective_rules.file_types
  return types.length ? `File types: ${types.join(", ")}` : "No file types"
}
