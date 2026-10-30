import type { ComponentProps } from "react"

type ButtonProps = ComponentProps<"button"> & {
  variant?: "primary" | "secondary"
}

const VARIANT_CLASSES = {
  primary:
    "border-primary bg-primary text-white hover:border-primary-hover hover:bg-primary-hover",
  secondary: "border-line-control bg-surface text-ink hover:bg-surface-subtle",
}

export function Button({
  variant = "primary",
  type = "button",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-control border px-4.5 font-medium transition-colors ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  )
}
