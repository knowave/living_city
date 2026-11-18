import { tileRectToWorld } from '../city-map/coords'

export type BuildingType = 'RESIDENTIAL' | 'COMMERCIAL' | 'OFFICE' | 'PUBLIC'

interface Building {
  id: string
  type: BuildingType
  tileX: number
  tileY: number
  width: number
  height: number // footprint depth in tiles
}

const STYLE: Record<BuildingType, { color: string; boxHeight: number }> = {
  RESIDENTIAL: { color: '#e8a87c', boxHeight: 2 },
  COMMERCIAL: { color: '#4fa3d9', boxHeight: 3 },
  OFFICE: { color: '#9b8bd1', boxHeight: 6 },
  PUBLIC: { color: '#e6c84f', boxHeight: 4 },
}

// Sample data; all footprints stay clear of the road row 20 and column 30.
const BUILDINGS: Building[] = [
  { id: 'b1', type: 'RESIDENTIAL', tileX: 24, tileY: 14, width: 2, height: 2 },
  { id: 'b2', type: 'RESIDENTIAL', tileX: 27, tileY: 15, width: 2, height: 3 },
  { id: 'b3', type: 'COMMERCIAL', tileX: 33, tileY: 15, width: 3, height: 3 },
  { id: 'b4', type: 'OFFICE', tileX: 38, tileY: 14, width: 3, height: 3 },
  { id: 'b5', type: 'PUBLIC', tileX: 24, tileY: 23, width: 4, height: 3 },
  { id: 'b6', type: 'COMMERCIAL', tileX: 33, tileY: 23, width: 2, height: 2 },
  { id: 'b7', type: 'OFFICE', tileX: 37, tileY: 23, width: 3, height: 4 },
  { id: 'b8', type: 'RESIDENTIAL', tileX: 20, tileY: 26, width: 2, height: 2 },
  { id: 'b9', type: 'RESIDENTIAL', tileX: 42, tileY: 24, width: 2, height: 2 },
  { id: 'b10', type: 'PUBLIC', tileX: 22, tileY: 10, width: 3, height: 2 },
]

export function Buildings() {
  return (
    <>
      {BUILDINGS.map((b) => {
        const { color, boxHeight } = STYLE[b.type]
        const [x, , z] = tileRectToWorld(b.tileX, b.tileY, b.width, b.height)
        return (
          <mesh key={b.id} position={[x, boxHeight / 2, z]}>
            <boxGeometry args={[b.width, boxHeight, b.height]} />
            <meshStandardMaterial color={color} />
          </mesh>
        )
      })}
    </>
  )
}
