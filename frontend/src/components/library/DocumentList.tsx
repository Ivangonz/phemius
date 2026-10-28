import type { DocumentListItem } from "@/hooks/useDocuments"
import { DocumentRow } from "./DocumentRow"

export function DocumentList({ documents }: { documents: DocumentListItem[] }) {
  return (
    <ul
      aria-label="Documents"
      className="divide-y divide-line overflow-hidden rounded-panel border border-line bg-surface"
    >
      {documents.map((document) => (
        <li key={document.id}>
          <DocumentRow document={document} />
        </li>
      ))}
    </ul>
  )
}
