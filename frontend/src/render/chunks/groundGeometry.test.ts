import { describe, expect, it } from 'vitest'
import { Dir, encodeRoad, ROAD_ISOLATED, RoadClass, tileIndex } from '../map/tiles'
import type { Chunk } from '../map/types'
import { buildGroundBuffers } from './groundGeometry'

function chunk(roads: [number, number, number][] = []): Chunk {
  const roadTiles = new Array(1024).fill(0)
  for (const [x, y, v] of roads) roadTiles[tileIndex(x, y)] = v
  return {
    id: 'c', worldId: 'w', chunkX: 1, chunkY: 2, chunkSize: 32, schemaVersion: 1, revision: 0,
    terrainTiles: new Array(1024).fill(0), roadTiles,
  }
}

describe('buildGroundBuffers', () => {
  it('terrain only: 1024 quads', () => {
    const b = buildGroundBuffers(chunk())
    expect(b.position.length / 3).toBe(4096)
    expect(b.index.length).toBe(6144)
  })
  it('normals, y layers, colors, index range', () => {
    const b = buildGroundBuffers(
      chunk([
        [0, 0, encodeRoad(RoadClass.LOCAL, Dir.N | Dir.E)],
        [5, 5, encodeRoad(RoadClass.ARTERIAL, Dir.N | Dir.E | Dir.S | Dir.W)],
        [9, 9, encodeRoad(RoadClass.LOCAL, ROAD_ISOLATED)],
      ]),
    )
    const n = b.position.length / 3
    expect(n).toBeGreaterThan(4096)
    expect(n).toBeLessThanOrEqual(24576)
    const ys = new Set<number>()
    for (let i = 0; i < n; i++) {
      expect([b.normal[i * 3], b.normal[i * 3 + 1], b.normal[i * 3 + 2]]).toEqual([0, 1, 0])
      ys.add(Math.round(b.position[i * 3 + 1] * 100) / 100)
    }
    expect([...ys].every((y) => [0, 0.02, 0.04].includes(y))).toBe(true)
    expect(ys.size).toBe(3)
    for (const c of b.color) expect(c >= 0 && c <= 1).toBe(true)
    expect(Math.max(...b.index)).toBe(n - 1)
  })
  it('worst case stays under Uint16 limit', () => {
    const all = encodeRoad(RoadClass.ARTERIAL, 15)
    const roads: [number, number, number][] = []
    for (let i = 0; i < 1024; i++) roads.push([i % 32, Math.floor(i / 32), all])
    expect(buildGroundBuffers(chunk(roads)).position.length / 3).toBe(4096 + 1024 * 5 * 4)
  })
  it('road tile draws a full-tile quad at Y_ROAD', () => {
    // chunk (1, 2) origin = (32, 64); road at local (3, 4)
    const b = buildGroundBuffers(chunk([[3, 4, encodeRoad(RoadClass.LOCAL, Dir.N | Dir.E)]]))
    const xs: number[] = []
    const zs: number[] = []
    for (let i = 0; i < b.position.length / 3; i++) {
      if (Math.round(b.position[i * 3 + 1] * 100) !== 2) continue
      xs.push(b.position[i * 3])
      zs.push(b.position[i * 3 + 2])
    }
    expect(xs.length).toBe(4)
    expect([Math.min(...xs), Math.max(...xs)]).toEqual([35, 36])
    expect([Math.min(...zs), Math.max(...zs)]).toEqual([68, 69])
  })
})
