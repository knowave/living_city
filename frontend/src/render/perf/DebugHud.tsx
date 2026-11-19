import { useEffect, useState } from 'react'
import type { CitizenLayerApi } from '../citizens/CitizenLayer'
import type { DebugStats } from './DebugMeter'
import { CHUNKS_PER_SIDE } from '../map/types'

export function DebugHud({
  statsRef,
  apiRef,
}: {
  statsRef: { current: DebugStats | null }
  apiRef: { current: CitizenLayerApi }
}) {
  const [stats, setStats] = useState<DebugStats | null>(null)
  const [cit, setCit] = useState<string[]>([])

  // Polls the ref so stats updates re-render only this HUD, never the Canvas tree.
  useEffect(() => {
    const id = setInterval(() => {
      setStats(statsRef.current)
      const { system: sys, cpu } = apiRef.current
      setCit(
        sys
          ? [
              `Citizens ${sys.visibleCount}/${sys.total}`,
              `Tick ${sys.lastTick.toFixed(1)}`,
              `Speed ${sys.speed}x`,
              `Cit CPU ${cpu.avg.toFixed(2)}/${cpu.max.toFixed(2)} ms`,
              `Path q${sys.perf.pathQueue} miss${sys.perf.pathMisses}`,
            ]
          : [],
      )
    }, 500)
    return () => clearInterval(id)
  }, [statsRef, apiRef])

  return (
    <div className="pointer-events-none absolute right-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      {stats ? (
        <>
          <div>FPS {stats.fps.toFixed(1)}</div>
          <div>Avg {stats.avg.toFixed(1)}</div>
          <div>
            Chunks {stats.activeChunks}/{CHUNKS_PER_SIDE ** 2} (+{stats.pendingChunks})
          </div>
          <div>Calls {stats.calls}</div>
          <div>Tris {stats.triangles}</div>
          <div>Geom {stats.geometries}</div>
          <div>Tex {stats.textures}</div>
          {cit.map((l) => (
            <div key={l}>{l}</div>
          ))}
        </>
      ) : (
        'FPS --'
      )}
    </div>
  )
}
