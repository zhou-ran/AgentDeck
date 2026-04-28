import { useSSE } from './hooks/useSSE'
import { Dashboard } from './components/Dashboard'

export default function App() {
  const { tasks, connected } = useSSE()

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-800 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <h1 className="text-base font-bold tracking-tight">
            <span className="text-cyan-400">Agent</span>Status
          </h1>
          <span className="text-gray-600 text-xs">Agent Supervisor Dashboard</span>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Dashboard tasks={tasks} connected={connected} />
      </main>
    </div>
  )
}
