import { describe, expect, it } from 'vitest'
import { BUILDINGS } from './buildingData'

const ROAD_ROW = 20
const ROAD_COL = 30
const SIZE = 64

describe('BUILDINGS', () => {
  it('has 20 buildings with unique ids', () => {
    expect(BUILDINGS).toHaveLength(20)
    expect(new Set(BUILDINGS.map((b) => b.id)).size).toBe(20)
  })

  it('stays within the map and off the roads', () => {
    for (const b of BUILDINGS) {
      expect(b.tileX).toBeGreaterThanOrEqual(0)
      expect(b.tileY).toBeGreaterThanOrEqual(0)
      expect(b.tileX + b.width).toBeLessThanOrEqual(SIZE)
      expect(b.tileY + b.height).toBeLessThanOrEqual(SIZE)
      expect(b.tileX <= ROAD_COL && ROAD_COL < b.tileX + b.width).toBe(false)
      expect(b.tileY <= ROAD_ROW && ROAD_ROW < b.tileY + b.height).toBe(false)
    }
  })

  it('has no overlapping footprints', () => {
    for (const [i, a] of BUILDINGS.entries()) {
      for (const b of BUILDINGS.slice(i + 1)) {
        const overlap =
          a.tileX < b.tileX + b.width &&
          b.tileX < a.tileX + a.width &&
          a.tileY < b.tileY + b.height &&
          b.tileY < a.tileY + a.height
        expect(overlap, `${a.id} vs ${b.id}`).toBe(false)
      }
    }
  })
})
