import { useId, useRef } from "react"
import { describeRule, type RuleView } from "@/lib/importRules"
import { RuleOrigin } from "./RuleOrigin"

type RuleSwitchProps = {
  label: string
  rule: RuleView<boolean>
  onChange: (value: boolean | null) => void
}

export function RuleSwitch({ label, rule, onChange }: RuleSwitchProps) {
  const originId = useId()
  const input = useRef<HTMLInputElement>(null)
  const state = { value: rule.value ? "On" : "Off", isOwn: rule.isOwn }

  function handleReset() {
    onChange(null)
    input.current?.focus()
  }

  return (
    <div className="flex flex-col gap-0.5 py-1">
      <label className="flex min-h-11 cursor-pointer items-start gap-3 py-1.5 leading-snug">
        <input
          ref={input}
          type="checkbox"
          role="switch"
          checked={rule.value}
          aria-describedby={originId}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-0.5 size-4.5 flex-none accent-primary"
        />
        <span>{label}</span>
      </label>
      <RuleOrigin
        id={originId}
        label={label}
        description={describeRule(state)}
        isOwn={rule.isOwn}
        onReset={handleReset}
      />
    </div>
  )
}
