import type { components } from "./api-schema"

export type SettingsOverview = components["schemas"]["SettingsOverview"]
export type SettingsUpdate = components["schemas"]["Settings"]

export type ProviderTag = "Cloud" | "Your server" | "Local"

export type ProviderOption = {
  id: string
  label: string
  tag: ProviderTag
  description: string
}

export function isLocked(overview: SettingsOverview, key: string): boolean {
  return (
    overview.values[key]?.is_locked ?? overview.secrets[key]?.is_locked ?? false
  )
}

export function savedValue(overview: SettingsOverview, key: string): string {
  const value = overview.values[key]?.value
  return value === null || value === undefined ? "" : String(value)
}
