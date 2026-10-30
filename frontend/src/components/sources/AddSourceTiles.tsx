import { useId } from "react"

const COMING_SOON = [
  { label: "GitHub repository", description: "Import Markdown from a repo." },
  { label: "Confluence space", description: "Import pages from a space." },
  { label: "Web page or feed", description: "Import a URL or RSS feed." },
]

const TILE_CLASSES =
  "flex min-h-22 flex-[1_1_12rem] flex-col items-start gap-1 rounded-control border border-dashed border-line-dashed px-4 py-3.5 text-left"

type AddSourceTilesProps = { onAddFolder: () => void }

export function AddSourceTiles({ onAddFolder }: AddSourceTilesProps) {
  const titleId = useId()

  return (
    <section aria-labelledby={titleId} className="mt-1.5 flex flex-col gap-3">
      <h2
        id={titleId}
        className="text-secondary font-semibold tracking-wider text-muted uppercase"
      >
        Add another
      </h2>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onAddFolder}
          className={`${TILE_CLASSES} cursor-pointer hover:bg-surface`}
        >
          <span className="font-semibold">Folder</span>
          <span className="text-secondary text-muted">
            Watch a folder on this computer.
          </span>
        </button>
        {COMING_SOON.map((tile) => (
          <div key={tile.label} className={`${TILE_CLASSES} text-muted`}>
            <span className="font-semibold">{tile.label}</span>
            <span className="text-secondary">{tile.description}</span>
            <span className="text-small font-medium">Coming soon</span>
          </div>
        ))}
      </div>
    </section>
  )
}
