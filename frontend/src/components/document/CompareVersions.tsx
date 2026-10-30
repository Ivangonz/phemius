import { useState } from "react"
import type { AudioVersion } from "@/lib/audioVersions"
import { CompareColumn } from "./CompareColumn"

type CompareVersionsProps = {
  versions: AudioVersion[]
  first: AudioVersion
  second: AudioVersion
}

export function CompareVersions({
  versions,
  first,
  second,
}: CompareVersionsProps) {
  const [firstId, setFirstId] = useState(first.id)
  const [secondId, setSecondId] = useState(second.id)
  const find = (audioId: number, fallback: AudioVersion) =>
    versions.find((version) => version.id === audioId) ?? fallback

  return (
    <div className="flex flex-wrap gap-5">
      <CompareColumn
        label="First version"
        versions={versions}
        version={find(firstId, first)}
        onChange={setFirstId}
      />
      <CompareColumn
        label="Second version"
        versions={versions}
        version={find(secondId, second)}
        onChange={setSecondId}
      />
    </div>
  )
}
