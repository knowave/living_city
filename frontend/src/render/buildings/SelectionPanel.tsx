import type { CityMap } from '../map/types'
import { useRenderCount } from '../perf/renderCount'

export function SelectionPanel({ city, selectedId }: { city: CityMap; selectedId: string | null }) {
  useRenderCount('SelectionPanel')
  const b = selectedId ? city.buildingById.get(selectedId) : undefined
  return (
    <div className="pointer-events-none absolute left-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      {b ? `Selected: ${b.id} (${b.type ?? 'UNKNOWN'})` : 'Selected: none'}
    </div>
  )
}
