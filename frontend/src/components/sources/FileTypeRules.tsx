import { useId, useRef } from "react"
import {
  describeRule,
  fileTypeOptions,
  toggleFileType,
  type RuleView,
} from "@/lib/importRules"
import { RuleOrigin } from "./RuleOrigin"

type FileTypeRulesProps = {
  rule: RuleView<string[]>
  onChange: (types: string[] | null) => void
}

export function FileTypeRules({ rule, onChange }: FileTypeRulesProps) {
  const originId = useId()
  const fieldset = useRef<HTMLFieldSetElement>(null)
  const selected = rule.value
  const isOnlyOne = selected.length === 1
  const state = { ...rule, value: selected.join(", ") }

  function handleReset() {
    onChange(null)
    const inputs = fieldset.current?.querySelectorAll("input") ?? []
    Array.from(inputs)
      .find((input) => !input.disabled)
      ?.focus()
  }

  return (
    <fieldset
      ref={fieldset}
      aria-describedby={originId}
      className="mt-2 flex flex-col gap-1"
    >
      <legend className="text-small font-semibold tracking-wider text-muted uppercase">
        File types
      </legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {fileTypeOptions(selected).map((type) => (
          <label
            key={type}
            className="inline-flex min-h-11 cursor-pointer items-center gap-2 font-mono text-small"
          >
            <input
              type="checkbox"
              checked={selected.includes(type)}
              disabled={isOnlyOne && selected.includes(type)}
              onChange={(event) =>
                onChange(toggleFileType(selected, type, event.target.checked))
              }
              className="size-4.5 accent-primary"
            />
            {type}
          </label>
        ))}
      </div>
      {isOnlyOne && (
        <p className="text-secondary text-muted">
          A source imports at least one type.
        </p>
      )}
      <RuleOrigin
        id={originId}
        label="File types"
        description={describeRule(state, "Follows the default")}
        isOwn={rule.isOwn}
        onReset={handleReset}
      />
    </fieldset>
  )
}
