import { useLibraryConfig, type LibraryConfig } from "@/hooks/useLibraryConfig"
import { SidebarCheckWarning } from "./SidebarCheckWarning"

function describe(config: LibraryConfig | undefined, isError: boolean) {
  if (config) {
    return {
      scriptModel: config.llm ? config.model : "Offline, no script model",
      voice: [config.tts, config.default_voice].filter(Boolean).join(" · "),
    }
  }
  const placeholder = isError ? "Unavailable" : "Loading…"
  return { scriptModel: placeholder, voice: placeholder }
}

export function SidebarStatusCard() {
  const { data, isError } = useLibraryConfig()
  const { scriptModel, voice } = describe(data, isError)

  return (
    <div className="hidden flex-col gap-2.5 rounded-control bg-sidebar-card px-3 py-3.5 md:flex">
      <dl className="flex flex-col gap-2.5">
        <div>
          <dt className="text-label text-sidebar-label uppercase">
            Script model
          </dt>
          <dd className="mt-0.5 font-mono text-small wrap-anywhere text-sidebar-value">
            {scriptModel}
          </dd>
        </div>
        <div>
          <dt className="text-label text-sidebar-label uppercase">Voice</dt>
          <dd className="mt-0.5 font-mono text-small text-sidebar-value">
            {voice}
          </dd>
        </div>
      </dl>
      <SidebarCheckWarning />
    </div>
  )
}
