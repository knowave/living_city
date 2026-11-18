import { BUILDINGS } from './buildingData'

export function SelectionPanel({ selectedId }: { selectedId: string | null }) {
  const b = BUILDINGS.find((x) => x.id === selectedId)
  return (
    <div className="pointer-events-none absolute left-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      {b ? `Selected: ${b.id} (${b.type})` : 'Selected: none'}
    </div>
  )
}
