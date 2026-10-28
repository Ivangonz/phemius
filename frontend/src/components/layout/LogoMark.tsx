const BARS = [
  { x: 6, y: 11, height: 6 },
  { x: 10.4, y: 7, height: 14 },
  { x: 14.8, y: 9.5, height: 9 },
  { x: 19.2, y: 12.5, height: 3 },
]

export function LogoMark() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect width="28" height="28" rx="8" className="fill-primary" />
      {BARS.map((bar) => (
        <rect
          key={bar.x}
          x={bar.x}
          y={bar.y}
          width="2.6"
          height={bar.height}
          rx="1.3"
          fill="#FFFFFF"
        />
      ))}
    </svg>
  )
}
