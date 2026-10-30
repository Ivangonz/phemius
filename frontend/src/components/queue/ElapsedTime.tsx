import { useEffect, useState } from "react"
import { formatTime } from "@/lib/formatTime"

const TICK_MS = 1_000

function nowSeconds() {
  return Date.now() / 1000
}

type ElapsedTimeProps = {
  started: number | null
  finished: number | null
  isTicking: boolean
}

export function ElapsedTime({
  started,
  finished,
  isTicking,
}: ElapsedTimeProps) {
  const [now, setNow] = useState(nowSeconds)

  useEffect(() => {
    if (!isTicking) return
    const timer = window.setInterval(() => setNow(nowSeconds()), TICK_MS)
    return () => window.clearInterval(timer)
  }, [isTicking])

  if (started === null) return null
  const end = finished ?? (isTicking ? now : null)
  if (end === null) return null

  return (
    <span className="font-mono">
      <span className="sr-only">Elapsed </span>
      {formatTime(end - started)}
    </span>
  )
}
