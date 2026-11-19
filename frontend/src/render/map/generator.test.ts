import { describe, expect, it } from 'vitest'
import { DEFAULT_SEED, MOCK_BUILDING_STATUS, generateWorld } from './generator'
import { buildRoadGrid, entranceTile } from '../citizens/roadGrid'
import { toCityMap } from './mapper'
import { Dir, MAP_SIZE, Terrain, decodeRoad, isKnownRoad, isKnownTerrain } from './tiles'
import { CHUNK_SIZE } from './types'

const t0 = performance.now()
const world = generateWorld(DEFAULT_SEED)
const genMs = performance.now() - t0

function globalGrid(w: typeof world, key: 'terrain_tiles' | 'road_tiles') {
  const g = new Uint8Array(MAP_SIZE * MAP_SIZE)
  for (const c of w.chunks)
    for (let i = 0; i < 1024; i++) {
      const x = c.chunk_x * CHUNK_SIZE + (i % CHUNK_SIZE)
      const y = c.chunk_y * CHUNK_SIZE + Math.floor(i / CHUNK_SIZE)
      g[y * MAP_SIZE + x] = c[key][i]
    }
  return g
}

describe('generateWorld', () => {
  it('is deterministic per seed', () => {
    expect(generateWorld(DEFAULT_SEED)).toEqual(world)
    expect(generateWorld(2)).not.toEqual(world)
  })

  it('emits 256 well-formed chunks', () => {
    expect(world.chunks).toHaveLength(256)
    const keys = new Set(world.chunks.map((c) => `${c.chunk_x},${c.chunk_y}`))
    expect(keys.size).toBe(256)
    const ids = new Set(world.chunks.map((c) => c.id))
    expect(ids.size).toBe(256)
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
    expect(world.chunks[0].world_id).toMatch(uuid)
    for (const c of world.chunks) {
      expect(c.world_id).toBe(world.chunks[0].world_id)
      expect(c.id).toMatch(uuid)
      expect([c.chunk_size, c.schema_version, c.revision]).toEqual([32, 1, 1])
      expect(c.terrain_tiles).toHaveLength(1024)
      expect(c.road_tiles).toHaveLength(1024)
      expect(c.terrain_tiles.every(isKnownTerrain)).toBe(true)
      expect(c.road_tiles.every(isKnownRoad)).toBe(true)
    }
  })

  it('road connections match neighbors across chunk borders', () => {
    const road = globalGrid(world, 'road_tiles')
    const has = (x: number, y: number) => x >= 0 && y >= 0 && x < MAP_SIZE && y < MAP_SIZE && road[y * MAP_SIZE + x] !== 0
    let roads = 0
    for (let y = 0; y < MAP_SIZE; y++)
      for (let x = 0; x < MAP_SIZE; x++) {
        const d = decodeRoad(road[y * MAP_SIZE + x])
        if (!d) continue
        roads++
        const expected =
          (has(x, y - 1) ? Dir.N : 0) | (has(x + 1, y) ? Dir.E : 0) | (has(x, y + 1) ? Dir.S : 0) | (has(x - 1, y) ? Dir.W : 0)
        expect(d.connection).toBe(expected || 16)
      }
    expect(roads).toBeGreaterThan(1000)
  })

  it('places valid non-overlapping buildings', () => {
    const terrain = globalGrid(world, 'terrain_tiles')
    const road = globalGrid(world, 'road_tiles')
    const occ = new Uint8Array(MAP_SIZE * MAP_SIZE)
    expect(world.buildings.length).toBeGreaterThanOrEqual(4000)
    expect(new Set(world.buildings.map((b) => b.id)).size).toBe(world.buildings.length)
    for (const b of world.buildings) {
      expect(b.status).toBe(MOCK_BUILDING_STATUS)
      expect(Math.max(b.width, b.height)).toBeLessThanOrEqual(6)
      expect(b.tile_x + b.width).toBeLessThanOrEqual(MAP_SIZE)
      expect(b.tile_y + b.height).toBeLessThanOrEqual(MAP_SIZE)
      expect(b.occupied_capacity).toBeLessThanOrEqual(b.capacity)
      for (let y = b.tile_y; y < b.tile_y + b.height; y++)
        for (let x = b.tile_x; x < b.tile_x + b.width; x++) {
          const i = y * MAP_SIZE + x
          if (road[i] !== 0 || terrain[i] === Terrain.WATER || occ[i]) throw new Error(`bad tile ${x},${y} for ${b.id}`)
          occ[i] = 1
        }
    }
  })

  it('every building entrance is in the main road component', () => {
    const map = toCityMap(world, () => {})
    const grid = buildRoadGrid(map)
    for (const b of map.buildingById.values()) {
      const e = entranceTile(grid, b)
      expect(e).toBeGreaterThanOrEqual(0)
      expect(grid.component[e]).toBe(grid.main)
    }
  })

  it('maps cleanly and reports timing', () => {
    const warns: string[] = []
    const map = toCityMap(world, (m) => warns.push(m))
    expect(warns).toEqual([])
    expect(map.chunks.size).toBe(256)
    expect(map.buildingById.size).toBe(world.buildings.length)
    console.log(`generateWorld(${DEFAULT_SEED}): ${genMs.toFixed(0)} ms, ${world.buildings.length} buildings`)
    expect(genMs).toBeLessThan(300)
  })

  it('has lakes, rivers and beaches in the target ratio', () => {
    const terrain = globalGrid(world, 'terrain_tiles')
    const count = (t: number) => terrain.reduce((n, v) => n + (v === t ? 1 : 0), 0)
    const total = MAP_SIZE * MAP_SIZE
    expect(count(Terrain.WATER) / total).toBeGreaterThanOrEqual(0.06)
    expect(count(Terrain.WATER) / total).toBeLessThanOrEqual(0.12)
    expect(count(Terrain.SAND) / total).toBeGreaterThanOrEqual(0.025)
    expect(count(Terrain.SAND) / total).toBeLessThanOrEqual(0.07)
  })
})
