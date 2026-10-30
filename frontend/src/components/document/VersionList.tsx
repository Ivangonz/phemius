import type { AudioVersion } from "@/lib/audioVersions"
import { VersionButton } from "./VersionButton"

type VersionListProps = {
  versions: AudioVersion[]
  selectedId: number | null
  onSelect: (audioId: number) => void
}

export function VersionList({
  versions,
  selectedId,
  onSelect,
}: VersionListProps) {
  return (
    <ul aria-label="Versions" className="flex flex-wrap gap-2">
      {versions.map((version) => (
        <li key={version.id}>
          <VersionButton
            version={version}
            isSelected={version.id === selectedId}
            onSelect={onSelect}
          />
        </li>
      ))}
    </ul>
  )
}
