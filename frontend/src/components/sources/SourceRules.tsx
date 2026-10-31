import { useId } from "react"
import { useUpdateRules, type SourceView } from "@/hooks/useSources"
import type { components } from "@/lib/api-schema"
import {
  fileTypesRule,
  SWITCH_RULES,
  switchRule,
  type SwitchRule,
} from "@/lib/importRules"
import { FileTypeRules } from "./FileTypeRules"
import { RuleSwitch } from "./RuleSwitch"
import { SaveError } from "./SaveError"

type ImportRules = components["schemas"]["ImportRules"]

type SourceRulesProps = { source: SourceView }

export function SourceRules({ source }: SourceRulesProps) {
  const titleId = useId()
  const { save, pending, error, isSaving } = useUpdateRules(source.id)

  function saveSwitch(key: SwitchRule, value: boolean | null) {
    const rules: ImportRules = {}
    rules[key] = value
    save(rules)
  }

  return (
    <section
      aria-labelledby={titleId}
      className="flex min-w-0 flex-[1_1_18rem] flex-col gap-1 rounded-control border border-line bg-surface-subtle p-4"
    >
      <h3 id={titleId} className="mb-1 font-semibold">
        Import rules
      </h3>
      {SWITCH_RULES.map(({ key, label }) => (
        <RuleSwitch
          key={key}
          label={label}
          rule={switchRule(source, key, pending)}
          onChange={(value) => saveSwitch(key, value)}
        />
      ))}
      <FileTypeRules
        rule={fileTypesRule(source, pending)}
        onChange={(types) => save({ file_types: types })}
      />
      <p role="status" className="text-secondary text-muted">
        {isSaving ? "Saving…" : ""}
      </p>
      {error !== null && <SaveError error={error} />}
    </section>
  )
}
