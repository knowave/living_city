import { describe, expect, it } from 'vitest'
import { DEFAULT_SEED, generateWorld } from '../map/generator'
import { toCityMap } from '../map/mapper'
import { Dir, MAP_SIZE, Terrain, decodeRoad } from '../map/tiles'
import { CHUNK_SIZE } from '../map/types'
import { PathService } from './PathService'
import { findPath } from './pathFinder'
import { buildRoadGrid, entranceTile } from './roadGrid'
import { samplePolyline, straightPolyline, toSidewalk } from './sidewalk'

const N = MAP_SIZE
const dto = generateWorld(DEFAULT_SEED)
const city = toCityMap(dto, () => {})
const grid = buildRoadGrid(city)
const buildings = [...city.buildingById.values()]
const terrain = new Uint8Array(N * N)
for (const c of dto.chunks)
  for (let i = 0; i < 1024; i++) terrain[(c.chunk_y * CHUNK_SIZE + Math.floor(i / CHUNK_SIZE)) * N + c.chunk_x * CHUNK_SIZE + (i % CHUNK_SIZE)] = c.terrain_tiles[i]

function pair(i: number) {
  // deterministic pair of nearby same-component buildings
  const a = buildings[(i * 7919) % buildings.length]
  const b = buildings[(i * 7919 + 1 + (i % 40)) % buildings.length]
  return [a, b] as const
}

describe('roadGrid', () => {
  it('conn bits match neighbours and entrance is deterministic', () => {
    for (let t = 0; t < N * N; t += 7) {
      if (grid.component[t] < 0) {
        expect(grid.conn[t]).toBe(0)
        continue
      }
      if (grid.conn[t] & Dir.E) expect(grid.conn[t + 1] & Dir.W).toBeTruthy()
      if (grid.conn[t] & Dir.S) expect(grid.conn[t + N] & Dir.N).toBeTruthy()
    }
    const b = buildings[0]
    expect(entranceTile(grid, b)).toBe(entranceTile(grid, b))
    expect(grid.component[entranceTile(grid, b)]).toBe(grid.main)
  })
})

describe('findPath', () => {
  it('walks only road tiles, 4-adjacent, along connection bits, entrance to entrance', () => {
    let longest = 0
    for (let i = 0; i < 50; i++) {
      const [a, b] = pair(i)
      const from = entranceTile(grid, a)
      const to = entranceTile(grid, b)
      const p = findPath(grid, from, to)!
      expect(p).not.toBeNull()
      expect([p[0], p[p.length - 1]]).toEqual([from, to])
      for (let k = 0; k < p.length; k++) {
        expect(grid.component[p[k]]).toBe(grid.main)
        if (k === 0) continue
        const d = p[k] - p[k - 1]
        const bit = d === -N ? Dir.N : d === 1 ? Dir.E : d === N ? Dir.S : d === -1 ? Dir.W : 0
        expect(bit).not.toBe(0)
        expect(grid.conn[p[k - 1]] & bit).toBe(bit)
      }
      longest = Math.max(longest, p.length)
    }
    expect(longest).toBeGreaterThan(5)
  })

  it('returns null across components and [t] for same tile', () => {
    let island = -1
    for (let t = 0; t < N * N; t++) if (grid.component[t] >= 0 && grid.component[t] !== grid.main) { island = t; break }
    const e = entranceTile(grid, buildings[0])
    if (island >= 0) expect(findPath(grid, e, island)).toBeNull()
    expect(findPath(grid, e, e)).toEqual(Int32Array.of(e))
    const water = terrain.findIndex((v, i) => v === Terrain.WATER && grid.component[i] < 0)
    expect(findPath(grid, e, water)).toBeNull()
  })

  it('crosses water on a bridge', () => {
    const bridge = [...Array(N * N).keys()].find((i) => terrain[i] === Terrain.WATER && grid.component[i] === grid.main)
    expect(bridge).toBeDefined()
    expect(decodeRoad(dto.chunks.find((c) => c.chunk_x === Math.floor((bridge! % N) / 32) && c.chunk_y === Math.floor(bridge! / N / 32))!.road_tiles[(Math.floor(bridge! / N) % 32) * 32 + ((bridge! % N) % 32)])).not.toBeNull()
  })

  it('benchmark: 1000 pairs within +-2 chunks', () => {
    const ms: number[] = []
    for (let i = 0, n = 0; n < 1000 && i < 100000; i++) {
      const a = buildings[(i * 104729) % buildings.length]
      const b = buildings[(i * 1299709 + 13) % buildings.length]
      if (Math.abs(a.tileX - b.tileX) > 64 || Math.abs(a.tileY - b.tileY) > 64) continue
      const from = entranceTile(grid, a)
      const to = entranceTile(grid, b)
      const t0 = performance.now()
      const p = findPath(grid, from, to)
      ms.push(performance.now() - t0)
      if (p) toSidewalk(p)
      n++
    }
    ms.sort((x, y) => x - y)
    const avg = ms.reduce((s, v) => s + v, 0) / ms.length
    console.log(`A* n=${ms.length} avg ${avg.toFixed(3)} ms, p99 ${ms[Math.floor(ms.length * 0.99)].toFixed(3)} ms`)
    expect(ms.length).toBeGreaterThan(500)
    expect(avg).toBeLessThanOrEqual(1)
  })
})

describe('sidewalk', () => {
  it('offsets to the right of travel with a mitered corner', () => {
    // east along row 10 then south: tiles (10,10) (11,10) (12,10) (12,11) (12,12)
    const p = Int32Array.from([10 * N + 10, 10 * N + 11, 10 * N + 12, 11 * N + 12, 12 * N + 12])
    const s = toSidewalk(p, 0.35)
    expect(s.xs).toHaveLength(3)
    // east-moving: right = +z (south) -> z = 10.5 + 0.35; start x unchanged
    expect(s.xs[0]).toBeCloseTo(10.5)
    expect(s.zs[0]).toBeCloseTo(10.85)
    // corner: right of east is +z, right of south is -x -> (12.5-0.35, 10.5+0.35)
    expect(s.xs[1]).toBeCloseTo(12.15)
    expect(s.zs[1]).toBeCloseTo(10.85)
    expect(s.xs[2]).toBeCloseTo(12.15)
    expect(s.zs[2]).toBeCloseTo(12.5)
    expect(s.length).toBeCloseTo(3.3)
    const o = { x: 0, z: 0, heading: 0 }
    samplePolyline(s, 1, o)
    expect(o.x).toBeCloseTo(11.5)
    expect(o.heading).toBeCloseTo(Math.PI / 2)
    samplePolyline(s, 99, o)
    expect(o.z).toBeCloseTo(12.5)
  })

  it('straight polyline joins entrance centres', () => {
    const s = straightPolyline(3 * N + 4, 3 * N + 8)
    expect(s.length).toBeCloseTo(4)
  })
})

describe('PathService', () => {
  const [a, b] = pair(3)
  const [c, d] = pair(4)
  const make = (max?: number) => {
    const svc = new PathService(grid, city, max)
    const got: [number, unknown][] = []
    svc.onResolved = (i, p) => got.push([i, p])
    return { svc, got }
  }

  it('is idempotent per citizen, shares work via cache', () => {
    const { svc, got } = make()
    svc.request(1, a.id, b.id)
    svc.request(1, a.id, b.id)
    svc.request(2, a.id, b.id)
    expect(svc.stats.queued).toBe(2)
    expect(svc.drain(1000)).toBe(2)
    expect(got.map((g) => g[0])).toEqual([1, 2])
    expect(got[0][1]).toBe(got[1][1])
    expect(svc.stats.misses).toBe(1)
    expect(svc.stats.cacheHits).toBe(1)
    svc.request(1, a.id, b.id) // already resolved: ignored
    expect(got).toHaveLength(2)
    svc.request(3, a.id, b.id) // cache hit resolves immediately
    expect(got).toHaveLength(3)
  })

  it('cancel removes queued request', () => {
    const { svc, got } = make()
    svc.request(1, a.id, b.id)
    svc.cancel(1)
    expect(svc.drain(1000)).toBe(0)
    expect(got).toHaveLength(0)
    expect(svc.stats.cancelled).toBe(1)
  })

  it('respects count and time budget, at least one per drain', () => {
    const { svc } = make()
    for (let i = 0; i < 5; i++) svc.request(i, buildings[i * 50].id, buildings[i * 50 + 3].id)
    expect(svc.drain(1000, undefined, 2)).toBe(2)
    let t = 0
    expect(svc.drain(1, () => (t += 2))).toBe(1) // clock jumps past budget after the first
    expect(svc.stats.queued).toBe(2)
  })

  it('evicts least recently used beyond max', () => {
    const { svc } = make(1)
    svc.request(1, a.id, b.id)
    svc.request(2, c.id, d.id)
    svc.drain(1000)
    expect(svc.stats.cacheSize).toBe(1)
    svc.request(3, a.id, b.id)
    expect(svc.stats.queued).toBe(1) // evicted -> miss
  })
})
