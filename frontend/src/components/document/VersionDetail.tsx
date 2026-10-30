import { RowPlayButton } from "@/components/library/RowPlayButton"
import { StatusBadge } from "@/components/library/StatusBadge"
import { useAudio, type AudioDetail } from "@/hooks/useAudio"
import { useVersionStatus } from "@/hooks/useVersionStatus"
import {
  describeVersion,
  formatDate,
  type AudioVersion,
} from "@/lib/audioVersions"
import { formatBytes } from "@/lib/formatBytes"
import { ScriptView } from "./ScriptView"

type VersionDetailProps = {
  version: AudioVersion
  title: string
}

function describeFile(audio: AudioDetail | undefined): string[] {
  if (!audio) return []
  const parts = [`Made ${formatDate(audio.created)}`]
  if (audio.format && audio.size_bytes !== null)
    parts.push(
      `${audio.format.toUpperCase()} · ${formatBytes(audio.size_bytes)}`,
    )
  return parts
}

export function VersionDetail({ version, title }: VersionDetailProps) {
  const { data: audio } = useAudio(version.id)
  const status = useVersionStatus(version)
  const textVersion =
    version.version === null ? [] : [`Text version ${version.version}`]
  const meta = [...describeFile(audio), ...textVersion].join(" · ")

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        {version.status === "done" ? (
          <RowPlayButton
            track={{
              audioId: version.id,
              title,
              meta: describeVersion(version),
            }}
          />
        ) : (
          <StatusBadge label={status.label} kind={status.kind} />
        )}
        <p className="font-mono text-small text-muted">{meta}</p>
      </div>
      {audio?.conversion_note && (
        <p className="text-secondary text-muted">{audio.conversion_note}</p>
      )}
      {version.error && (
        <div role="alert" className="text-danger-ink">
          <p>{version.error}</p>
          {version.hint && <p className="text-muted">{version.hint}</p>}
        </div>
      )}
      <ScriptView script={audio?.script ?? null} version={version} />
    </div>
  )
}
