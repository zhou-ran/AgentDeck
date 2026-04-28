import type { CpuMemSample } from '../types'

interface SparkLineProps {
  data: CpuMemSample[]
  width?: number
  height?: number
  showLegend?: boolean
}

function buildPath(data: number[], width: number, height: number, maxVal: number): string {
  if (data.length < 2) return ''
  const step = width / (data.length - 1)
  const effectiveMax = maxVal || 100
  return data
    .map((v, i) => {
      const x = i * step
      const y = height - (v / effectiveMax) * height
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export function SparkLine({ data, width = 200, height = 40, showLegend = true }: SparkLineProps) {
  if (!data || data.length < 2) {
    return (
      <div className="text-gray-600 text-[10px] italic" style={{ height }}>
        collecting data...
      </div>
    )
  }

  const cpuValues = data.map((d) => d.cpu)
  const memValues = data.map((d) => d.mem)
  const maxCpu = Math.max(1, ...cpuValues)
  const maxMem = Math.max(1, ...memValues)

  const cpuPath = buildPath(cpuValues, width, height, maxCpu)
  const memPath = buildPath(memValues, width, height, maxMem)

  const lastCpu = cpuValues[cpuValues.length - 1]
  const lastMem = memValues[memValues.length - 1]

  return (
    <div>
      <svg width={width} height={height} className="block">
        {/* CPU line - green */}
        <path d={cpuPath} fill="none" stroke="#22c55e" strokeWidth="1.5" />
        {/* MEM line - blue */}
        <path d={memPath} fill="none" stroke="#3b82f6" strokeWidth="1.5" />
      </svg>
      {showLegend && (
        <div className="flex gap-3 text-[10px] mt-0.5">
          <span className="text-green-400">CPU {lastCpu.toFixed(1)}%</span>
          <span className="text-blue-400">MEM {lastMem.toFixed(1)}%</span>
        </div>
      )}
    </div>
  )
}
