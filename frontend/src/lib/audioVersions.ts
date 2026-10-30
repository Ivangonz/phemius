import type { components } from "./api-schema"

export type AudioVersion = components["schemas"]["AudioSummary"]
type VersionSummary = components["schemas"]["VersionSummary"]

export function listAudioVersions(versions: VersionSummary[]): AudioVersion[] {
  return versions.flatMap((version) => version.audio)
}

// The backend marks a document changed when a watched file was updated in
// `mark` mode: older text has audio, the newest text has none yet.
export function isDocumentChanged(versions: VersionSummary[]): boolean {
  const [latest, ...older] = versions
  return (
    latest !== undefined &&
    latest.audio.length === 0 &&
    older.some((version) => version.audio.length > 0)
  )
}

export function formatDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString(undefined, {
    dateStyle: "medium",
  })
}
