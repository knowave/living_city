import { describe, expect, it } from 'vitest'
import { chunkKey, chunkLocalToWorld, decodeRoad, encodeRoad, isKnownRoad, tileIndex, worldToChunk } from './tiles'

describe('tiles', () => {
  it('tileIndex = localY*32+localX', () => {
    expect(tileIndex(0, 0)).toBe(0)
    expect(tileIndex(31, 0)).toBe(31)
    expect(tileIndex(0, 1)).toBe(32)
    expect(tileIndex(31, 31)).toBe(1023)
  })

  it('worldToChunk edges', () => {
    expect(worldToChunk(511, 32)).toEqual({ chunkX: 15, chunkY: 1, localX: 31, localY: 0 })
    expect(worldToChunk(31, 31)).toMatchObject({ chunkX: 0, chunkY: 0 })
    expect(worldToChunk(0, 32)).toMatchObject({ chunkY: 1, localY: 0 })
    expect(worldToChunk(511, 511)).toEqual({ chunkX: 15, chunkY: 15, localX: 31, localY: 31 })
  })

  it('world -> chunk -> world round trip', () => {
    for (let i = 0; i < 1000; i++) {
      const x = (i * 7919) % 512
      const y = (i * 104729) % 512
      const c = worldToChunk(x, y)
      expect(chunkLocalToWorld(c.chunkX, c.chunkY, c.localX, c.localY)).toEqual({ tileX: x, tileY: y })
    }
  })

  it('chunkKey', () => {
    expect(chunkKey(3, 15)).toBe('3,15')
  })

  it('road encode/decode', () => {
    expect(encodeRoad(1, 5)).toBe(37)
    expect(decodeRoad(37)).toEqual({ cls: 1, connection: 5 })
    expect(decodeRoad(encodeRoad(0, 16))).toEqual({ cls: 0, connection: 16 })
    expect(decodeRoad(0)).toBeNull()
  })

  it('isKnownRoad', () => {
    expect([0, 1, 15, 16, 33, 48].every(isKnownRoad)).toBe(true)
    expect([17, 32, 64 + 1, 99, -1, 1.5].some(isKnownRoad)).toBe(false)
  })
})
