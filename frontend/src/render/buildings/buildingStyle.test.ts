import { describe, expect, it } from 'vitest'
import type { Building } from '../map/types'
import { buildingTransform, DEFAULT_STYLE, STYLE } from './buildingStyle'

const base: Building = {
  id: 'a', worldId: 'w', type: 'RESIDENTIAL', tileX: 10, tileY: 20, width: 3, height: 2,
  capacity: 1, occupiedCapacity: 0, status: 'ACTIVE',
}

describe('buildingTransform', () => {
  it('centers the footprint and scales by style height', () => {
    expect(buildingTransform(base)).toEqual({
      position: [11.5, 0, 21],
      scale: [3, STYLE.RESIDENTIAL.boxHeight, 2],
    })
  })
  it('uses default style for null type', () => {
    expect(buildingTransform({ ...base, type: null }).scale[1]).toBe(DEFAULT_STYLE.boxHeight)
  })
})
