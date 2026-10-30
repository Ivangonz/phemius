import { PageHeader } from "@/components/PageHeader"
import { SourceList } from "./SourceList"

const DESCRIPTION =
  "Where documents come from. New and changed files are imported and narrated automatically."

export function SourcesPage() {
  return (
    <>
      <PageHeader title="Sources" description={DESCRIPTION} />
      <div className="flex flex-col gap-3.5">
        <SourceList />
      </div>
    </>
  )
}
