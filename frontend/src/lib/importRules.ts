import type { components } from "./api-schema"

type SourceView = components["schemas"]["SourceView"]
type ImportRules = components["schemas"]["ImportRules"]

export type SwitchRule =
  | "auto_audio"
  | "skip_not_recommended"
  | "keep_versions"
  | "regenerate_on_change"

export const SWITCH_RULES: { key: SwitchRule; label: string }[] = [
  {
    key: "auto_audio",
    label: "Generate audio automatically for new documents",
  },
  {
    key: "skip_not_recommended",
    label: 'Skip documents marked "not recommended for audio"',
  },
  {
    key: "keep_versions",
    label: "Keep earlier versions when a document changes",
  },
  {
    key: "regenerate_on_change",
    label: "Re-generate audio when a document changes",
  },
]

// The API does not list the types it can import; this mirrors ingest.SUPPORTED.
const KNOWN_FILE_TYPES = [
  ".md",
  ".markdown",
  ".txt",
  ".rst",
  ".html",
  ".htm",
  ".docx",
  ".pdf",
]

export type RuleView<T> = { value: T; isOwn: boolean }

// While a save is in flight, show what was sent rather than the stale source.
function ownRule<K extends keyof ImportRules>(
  source: SourceView,
  key: K,
  pending: ImportRules | undefined,
): ImportRules[K] {
  return pending && key in pending ? pending[key] : source.rules[key]
}

export function switchRule(
  source: SourceView,
  key: SwitchRule,
  pending: ImportRules | undefined,
): RuleView<boolean> {
  const own = ownRule(source, key, pending)
  return { value: own ?? source.effective_rules[key], isOwn: own != null }
}

export function fileTypesRule(
  source: SourceView,
  pending: ImportRules | undefined,
): RuleView<string[]> {
  const own = ownRule(source, "file_types", pending)
  return { value: own ?? source.effective_rules.file_types, isOwn: own != null }
}

export function fileTypeOptions(selected: string[]): string[] {
  const extra = selected.filter((type) => !KNOWN_FILE_TYPES.includes(type))
  return [...KNOWN_FILE_TYPES, ...extra]
}

export function toggleFileType(
  selected: string[],
  type: string,
  isChecked: boolean,
): string[] {
  const rest = selected.filter((item) => item !== type)
  return (isChecked ? [...rest, type] : rest).sort()
}

export function describeRule(rule: RuleView<string>): string {
  return rule.isOwn
    ? `This source: ${rule.value}`
    : `Follows global setting: ${rule.value}`
}
