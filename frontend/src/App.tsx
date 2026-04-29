import { useSSE } from './hooks/useSSE'
import { Dashboard } from './components/Dashboard'
import { demoScanMeta, demoSessions, demoSystemMetrics, demoTasks } from './mock/demoData'

export default function App() {
  const demoMode = new URLSearchParams(window.location.search).get('demo') === '1'
  const { tasks, discovered, systemMetrics, scanMeta, connected, error } = useSSE(!demoMode)

  const appTasks = demoMode ? demoTasks : tasks
  const appDiscovered = demoMode ? demoSessions : discovered
  const appSystemMetrics = demoMode ? demoSystemMetrics : systemMetrics
  const appScanMeta = demoMode ? demoScanMeta : scanMeta

  return (
    <div className="min-h-screen">
      {!demoMode && error && (
        <div className="fixed left-1/2 top-4 z-50 w-[min(680px,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700 shadow-lg backdrop-blur-xl dark:text-red-300">
          {error}
        </div>
      )}
      <Dashboard
        tasks={appTasks}
        discovered={appDiscovered}
        systemMetrics={appSystemMetrics}
        scanMeta={appScanMeta}
        connected={demoMode ? true : connected}
        demoMode={demoMode}
      />
    </div>
  )
}
