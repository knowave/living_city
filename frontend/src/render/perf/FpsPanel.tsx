import type { FpsStats } from './fps'

export function FpsPanel({ stats }: { stats: FpsStats | null }) {
  return (
    <div className="pointer-events-none absolute right-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      {stats ? (
        <>
          <div>FPS {stats.fps.toFixed(1)}</div>
          <div>Avg {stats.avg.toFixed(1)}</div>
        </>
      ) : (
        'FPS --'
      )}
    </div>
  )
}
