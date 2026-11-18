import { describe, expect, it } from 'vitest'
import { MAP_CENTER, tileRectToWorld } from './coords'

describe('tileRectToWorld', () => {
  it('maps a tile to its center on the XZ plane', () => {
    expect(tileRectToWorld(0, 0)).toEqual([0.5, 0, 0.5])
    expect(tileRectToWorld(3, 7)).toEqual([3.5, 0, 7.5])
  })
  it('maps a footprint rect to its center', () => {
    expect(tileRectToWorld(2, 4, 4, 2)).toEqual([4, 0, 5])
  })
  it('puts the map center at (32, 0, 32)', () => {
    expect(MAP_CENTER).toEqual([32, 0, 32])
  })
})
