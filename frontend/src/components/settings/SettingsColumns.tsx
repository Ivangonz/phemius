import type { ReactNode } from "react"

type SettingsColumnsProps = {
  left: ReactNode
  right: ReactNode
}

// Two columns of cards on wide screens, one column on a phone.
export function SettingsColumns({ left, right }: SettingsColumnsProps) {
  return (
    <div className="flex flex-wrap items-start gap-5">
      <div className="flex min-w-0 flex-[1_1_28rem] flex-col gap-5">{left}</div>
      <div className="flex min-w-0 flex-[1_1_28rem] flex-col gap-5">
        {right}
      </div>
    </div>
  )
}
