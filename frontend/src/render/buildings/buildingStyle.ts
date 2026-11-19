import type { Building, BuildingType } from '../map/types'
import type { Vec3 } from '../city-map/coords'

export const STYLE: Record<BuildingType, { color: string; boxHeight: number }> = {
  RESIDENTIAL: { color: '#e8a87c', boxHeight: 2 },
  COMMERCIAL: { color: '#4fa3d9', boxHeight: 3 },
  OFFICE: { color: '#9b8bd1', boxHeight: 6 },
  PUBLIC: { color: '#e6c84f', boxHeight: 4 },
}

export const DEFAULT_STYLE = { color: '#9e9e9e', boxHeight: 2 }

export function styleOf(b: Building) {
  return b.type ? STYLE[b.type] : DEFAULT_STYLE
}

// Unit box has its base at y=0, so position.y is 0 and scale carries the height.
export function buildingTransform(b: Building): { position: Vec3; scale: Vec3 } {
  const { boxHeight } = styleOf(b)
  return {
    position: [b.tileX + b.width / 2, 0, b.tileY + b.height / 2],
    scale: [b.width, boxHeight, b.height],
  }
}
