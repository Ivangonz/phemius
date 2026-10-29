import type { components } from "./api-schema"

type SetupCheck = components["schemas"]["SetupCheck"]
type CheckId = components["schemas"]["CheckId"]
type CheckStatus = components["schemas"]["CheckStatus"]
export type SettingsPath = "/settings" | "/settings/server"

export const CHECK_STATUS_LABELS: Record<CheckStatus, string> = {
  ok: "OK",
  optional: "Optional",
  needs_attention: "Needs attention",
}

const SETTINGS_PATHS: Record<CheckId, SettingsPath> = {
  script_model: "/settings",
  voice_engine: "/settings",
  python: "/settings/server",
  library: "/settings/server",
  watch_folder: "/settings/server",
  ffmpeg: "/settings/server",
}

export function settingsPathFor(id: CheckId): SettingsPath {
  return SETTINGS_PATHS[id]
}

export function needingAttention(checks: SetupCheck[]): SetupCheck[] {
  return checks.filter((check) => check.status === "needs_attention")
}

// Several problems in different sections go to the Server tab, where the
// setup checks card lists them all with their own links.
export function attentionPath(checks: SetupCheck[]): SettingsPath {
  const paths = new Set(checks.map((check) => settingsPathFor(check.id)))
  const [onlyPath] = paths
  return paths.size === 1 && onlyPath ? onlyPath : "/settings/server"
}

export function formatRunTime(ranAt: string): string {
  const date = new Date(ranAt)
  if (Number.isNaN(date.getTime())) return "an unknown time"
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  })
}
