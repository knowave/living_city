import { tileRectToWorld } from '../city-map/coords'
import { BUILDINGS, type BuildingType } from './buildingData'

const STYLE: Record<BuildingType, { color: string; boxHeight: number }> = {
  RESIDENTIAL: { color: '#e8a87c', boxHeight: 2 },
  COMMERCIAL: { color: '#4fa3d9', boxHeight: 3 },
  OFFICE: { color: '#9b8bd1', boxHeight: 6 },
  PUBLIC: { color: '#e6c84f', boxHeight: 4 },
}

const SELECTED_COLOR = '#ff4d4d'

interface BuildingsProps {
  selectedId: string | null
  onSelect: (id: string) => void
}

export function Buildings({ selectedId, onSelect }: BuildingsProps) {
  return (
    <>
      {BUILDINGS.map((b) => {
        const { color, boxHeight } = STYLE[b.type]
        const [x, , z] = tileRectToWorld(b.tileX, b.tileY, b.width, b.height)
        return (
          <mesh
            key={b.id}
            position={[x, boxHeight / 2, z]}
            onClick={(e) => {
              if (e.delta > 4) return // drag, not a click
              e.stopPropagation()
              onSelect(b.id)
            }}
          >
            <boxGeometry args={[b.width, boxHeight, b.height]} />
            <meshStandardMaterial color={b.id === selectedId ? SELECTED_COLOR : color} />
          </mesh>
        )
      })}
    </>
  )
}
