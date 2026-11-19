import { useEffect, useRef } from 'react'
import { useRenderCount } from '../perf/renderCount'
import type { CitizenLayerApi } from './CitizenLayer'

interface Props {
  citizenId: string | null
  apiRef: { current: CitizenLayerApi }
}

// Volatile fields are written via textContent on a timer: no React re-render while selected.
export function CitizenPanel({ citizenId, apiRef }: Props) {
  useRenderCount('CitizenPanel')
  const volatile = useRef<HTMLDivElement>(null)
  const fixed = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = volatile.current
    if (!el || !citizenId) return
    const sys0 = apiRef.current.system
    const c = sys0?.store.citizens[sys0.store.index.get(citizenId) ?? -1]
    if (fixed.current) fixed.current.textContent = c ? `Name: ${c.name}\nEmployment: ${c.employmentStatus}` : ''
    const write = () => {
      const sys = apiRef.current.system
      const i = sys?.store.index.get(citizenId)
      if (!sys || i === undefined) return
      const cur = sys.store.citizens[i]
      const e = sys.store.moving[i]
      el.textContent = [
        `Tick: ${sys.lastTick.toFixed(1)}`,
        `State: ${e ? 'moving' : 'idle'}`,
        `Activity: ${cur.currentActivity}`,
        `Building: ${cur.currentBuildingId ?? '-'}`,
        `Destination: ${cur.currentDestination ?? '-'}`,
        `Arrival tick: ${cur.arrivalTick ?? '-'}`,
      ].join('\n')
    }
    write()
    const id = setInterval(write, 500)
    return () => clearInterval(id)
  }, [citizenId, apiRef])

  if (!citizenId) return null
  return (
    <div className="pointer-events-none absolute left-2 top-10 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      <div>Citizen: {citizenId}</div>
      <div ref={fixed} className="whitespace-pre" />
      <div ref={volatile} className="whitespace-pre" />
    </div>
  )
}
