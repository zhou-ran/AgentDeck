import type { ReactNode } from 'react'
import { Sidebar, type SidebarItem, type ViewKey } from './Sidebar'
import { TopToolbar } from './TopToolbar'
import type { ScanMeta } from '../types'

export function AppShell({
  activeView,
  onViewChange,
  sidebarItems,
  projects,
  agents,
  search,
  onSearch,
  onRefresh,
  onOpenPalette,
  connected,
  scanMeta,
  sidebarStats,
  demoMode = false,
  children,
}: {
  activeView: ViewKey
  onViewChange: (view: ViewKey) => void
  sidebarItems: SidebarItem[]
  projects: string[]
  agents: string[]
  search: string
  onSearch: (value: string) => void
  onRefresh: () => void
  onOpenPalette?: () => void
  connected: boolean
  scanMeta: ScanMeta | null
  sidebarStats?: ReactNode
  demoMode?: boolean
  children: ReactNode
}) {
  return (
    <div className="min-h-screen">
      <Sidebar
        activeView={activeView}
        onViewChange={onViewChange}
        items={sidebarItems}
        projects={projects}
        agents={agents}
        stats={sidebarStats}
      />
      <div className="min-h-screen lg:pl-[264px]">
        <TopToolbar
          search={search}
          onSearch={onSearch}
          onRefresh={onRefresh}
          onOpenPalette={onOpenPalette}
          connected={connected}
          scanMeta={scanMeta}
          demoMode={demoMode}
        />
        <main className="mx-auto max-w-[1600px] px-4 py-5 sm:px-5 lg:px-6">
          {children}
        </main>
      </div>
    </div>
  )
}
