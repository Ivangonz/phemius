type MenuButtonProps = {
  isOpen: boolean
  controls: string
  onClick: () => void
}

export function MenuButton({ isOpen, controls, onClick }: MenuButtonProps) {
  return (
    <button
      type="button"
      aria-expanded={isOpen}
      aria-controls={controls}
      onClick={onClick}
      className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-nav px-3 font-medium text-sidebar-ink hover:bg-sidebar-active hover:text-white focus-visible:outline-sidebar-value md:hidden"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        aria-hidden="true"
      >
        {isOpen ? (
          <path d="M6 6l12 12M18 6L6 18" />
        ) : (
          <path d="M4 7h16M4 12h16M4 17h16" />
        )}
      </svg>
      Menu
    </button>
  )
}
