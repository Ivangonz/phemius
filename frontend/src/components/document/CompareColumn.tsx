import { useId } from "react"
import { useAudio } from "@/hooks/useAudio"
import { describeVersion, type AudioVersion } from "@/lib/audioVersions"
import { ScriptView } from "./ScriptView"

type CompareColumnProps = {
  label: string
  versions: AudioVersion[]
  version: AudioVersion
  onChange: (audioId: number) => void
}

function describeOption(version: AudioVersion): string {
  const text = version.version === null ? "" : ` · text v${version.version}`
  return `${describeVersion(version)}${text}`
}

export function CompareColumn({
  label,
  versions,
  version,
  onChange,
}: CompareColumnProps) {
  const id = useId()
  const { data: audio } = useAudio(version.id)

  return (
    <section
      aria-labelledby={`${id}-label`}
      className="flex min-w-0 flex-[1_1_280px] flex-col gap-3"
    >
      <label id={`${id}-label`} htmlFor={id} className="font-semibold">
        {label}
      </label>
      <select
        id={id}
        value={version.id}
        onChange={(event) => onChange(Number(event.target.value))}
        className="min-h-11 min-w-0 rounded-control border border-line-control bg-surface px-2.5"
      >
        {versions.map((option) => (
          <option key={option.id} value={option.id}>
            {describeOption(option)}
          </option>
        ))}
      </select>
      <ScriptView script={audio?.script ?? null} version={version} />
    </section>
  )
}
