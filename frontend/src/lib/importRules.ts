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

export type RuleView<T> = { value: T; isOwn: boolean; isResetting: boolean }

// While a save is in flight, show what was sent rather than the stale source.
function viewRule<K extends keyof ImportRules>(
  source: SourceView,
  key: K,
  pending: ImportRules | undefined,
) {
  const isSent = pending !== undefined && key in pending
  const own = isSent ? pending[key] : source.rules[key]
  return { own, isOwn: own != null, isResetting: isSent && own === null }
}

export function switchRule(
  source: SourceView,
  key: SwitchRule,
  pending: ImportRules | undefined,
): RuleView<boolean> {
  const { own, ...state } = viewRule(source, key, pending)
  return { value: own ?? source.effective_rules[key], ...state }
}

export function fileTypesRule(
  source: SourceView,
  pending: ImportRules | undefined,
): RuleView<string[]> {
  const { own, ...state } = viewRule(source, "file_types", pending)
  return { value: own ?? source.effective_rules.file_types, ...state }
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

// The global value is unknown until the server answers a reset.
export function describeRule(rule: RuleView<string>, follows: string): string {
  if (rule.isOwn) return `This source: ${rule.value}`
  return rule.isResetting ? follows : `${follows}: ${rule.value}`
}
