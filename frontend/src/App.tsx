import { useSSE } from './hooks/useSSE'
import { Dashboard } from './components/Dashboard'

export default function App() {
  const { tasks, discovered, systemMetrics, connected, error } = useSSE()

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-800 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <h1 className="text-base font-bold tracking-tight">
            <span className="text-cyan-400">本地牛马监工台</span>
          </h1>
          <span className="text-gray-600 text-xs">Local Agent Foreman</span>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-6">
        {error && (
          <div className="mb-4 rounded border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}
        <Dashboard tasks={tasks} discovered={discovered} systemMetrics={systemMetrics} connected={connected} />
      </main>
    </div>
  )
}
