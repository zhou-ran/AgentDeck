import type { ReactNode } from 'react'

export function EmptyState({
  icon,
  title,
  description,
      action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-3 grid h-10 w-10 place-items-center rounded-2xl border border-[var(--border)] bg-black/[0.025] text-muted dark:bg-white/[0.04]">
        {icon || <span className="h-3 w-3 rounded-full border border-[var(--border-strong)]" />}
      </div>
      <div className="text-sm font-semibold text-app">{title}</div>
      {description && <div className="mt-1 max-w-xs text-xs text-muted">{description}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function EmptyStatePanel({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="glass-panel-strong rounded-[22px] p-8">
      <EmptyState icon={icon} title={title} description={description} action={action} />
    </div>
  )
}
