export function CommandSearch({
  value,
  onChange,
  onOpenPalette,
  placeholder = 'Search tasks, projects, logs...',
}: {
  value: string
  onChange: (value: string) => void
  onOpenPalette?: () => void
  placeholder?: string
}) {
  return (
    <label className="group relative block min-w-0 flex-1">
      <button
        type="button"
        onClick={event => {
          event.preventDefault()
          onOpenPalette?.()
        }}
        className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full px-2 py-0.5 text-xs text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10"
        title="Open Command Palette"
      >
        ⌘K
      </button>
      <input
        id="session-filter"
        value={value}
        onChange={event => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-full border border-[var(--border)] bg-white/70 py-2 pl-14 pr-4 text-sm text-app shadow-sm outline-none placeholder:text-[var(--muted)] transition focus:border-[var(--blue)] focus:bg-white/90 dark:bg-white/10 dark:focus:bg-white/20"
      />
    </label>
  )
}
