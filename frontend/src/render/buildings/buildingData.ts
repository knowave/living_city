export type BuildingType = 'RESIDENTIAL' | 'COMMERCIAL' | 'OFFICE' | 'PUBLIC'

export interface Building {
  id: string
  type: BuildingType
  tileX: number
  tileY: number
  width: number
  height: number // footprint depth in tiles
}

// Sample data; all footprints stay clear of the road row 20 and column 30.
export const BUILDINGS: Building[] = [
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
  { id: 'b11', type: 'RESIDENTIAL', tileX: 5, tileY: 5, width: 2, height: 2 },
  { id: 'b12', type: 'COMMERCIAL', tileX: 12, tileY: 8, width: 3, height: 3 },
  { id: 'b13', type: 'OFFICE', tileX: 50, tileY: 6, width: 3, height: 3 },
  { id: 'b14', type: 'PUBLIC', tileX: 56, tileY: 12, width: 4, height: 3 },
  { id: 'b15', type: 'RESIDENTIAL', tileX: 8, tileY: 25, width: 2, height: 2 },
  { id: 'b16', type: 'COMMERCIAL', tileX: 14, tileY: 30, width: 3, height: 2 },
  { id: 'b17', type: 'OFFICE', tileX: 45, tileY: 30, width: 3, height: 4 },
  { id: 'b18', type: 'PUBLIC', tileX: 52, tileY: 26, width: 3, height: 3 },
  { id: 'b19', type: 'RESIDENTIAL', tileX: 35, tileY: 40, width: 2, height: 2 },
  { id: 'b20', type: 'COMMERCIAL', tileX: 22, tileY: 45, width: 3, height: 3 },
]
