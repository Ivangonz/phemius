type InstallButtonTextProps = {
  label: string
  isUnderway: boolean
  waitsFor: string | null
}

export function InstallButtonText({
  label,
  isUnderway,
  waitsFor,
}: InstallButtonTextProps) {
  if (isUnderway)
    return (
      <>
        Installing…<span className="sr-only"> {label}</span>
      </>
    )
  if (waitsFor)
    return (
      <>
        <span className="sr-only">Install {label}: </span>Waits for {waitsFor}
      </>
    )
  return (
    <>
      Install<span className="sr-only"> {label}</span>
    </>
  )
}
