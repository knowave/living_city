import { describe, expect, it, vi } from 'vitest'
import { toBuilding, toChunk, toCityMap } from './mapper'
import type { BuildingDTO, ChunkDTO } from './types'

const chunk = (x = 0, y = 0, over: Partial<ChunkDTO> = {}): ChunkDTO => ({
  id: `c${x}-${y}`,
  world_id: 'w',
  chunk_x: x,
  chunk_y: y,
  chunk_size: 32,
  terrain_tiles: new Array(1024).fill(0),
  road_tiles: new Array(1024).fill(0),
  schema_version: 1,
  revision: 1,
  ...over,
})
const bld = (id: string, over: Partial<BuildingDTO> = {}): BuildingDTO => ({
  id,
  world_id: 'w',
  type: 'OFFICE',
  tile_x: 5,
  tile_y: 6,
  width: 3,
  height: 4,
  capacity: 12,
  occupied_capacity: 2,
  status: 'ACTIVE',
  ...over,
})

describe('mapper', () => {
  it('maps chunk snake -> camel', () => {
    const c = toChunk(chunk(2, 3, { revision: 9, schema_version: 1 }), () => {})
    expect(c).toMatchObject({ id: 'c2-3', worldId: 'w', chunkX: 2, chunkY: 3, chunkSize: 32, schemaVersion: 1, revision: 9 })
    expect(c.terrainTiles).toHaveLength(1024)
  })

  it('maps building snake -> camel', () => {
    expect(toBuilding(bld('b'), () => {})).toEqual({
      id: 'b', worldId: 'w', type: 'OFFICE', tileX: 5, tileY: 6, width: 3, height: 4,
      capacity: 12, occupiedCapacity: 2, status: 'ACTIVE',
    })
  })

  it('throws on bad length or chunk_size', () => {
    expect(() => toChunk(chunk(0, 0, { terrain_tiles: [0] }), () => {})).toThrow()
    expect(() => toChunk(chunk(0, 0, { road_tiles: [] }), () => {})).toThrow()
    expect(() => toChunk(chunk(0, 0, { chunk_size: 16 }), () => {})).toThrow()
  })

  it('unknown tile values -> defaults, exactly one warning total', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const a = chunk(0, 0)
    a.terrain_tiles[3] = 7
    a.road_tiles[4] = 99
    const b = chunk(1, 0)
    b.terrain_tiles[0] = 9
    const m = toCityMap({ chunks: [a, b], buildings: [] })
    expect(m.chunks.get('0,0')!.terrainTiles[3]).toBe(0)
    expect(m.chunks.get('0,0')!.roadTiles[4]).toBe(0)
    expect(m.chunks.get('1,0')!.terrainTiles[0]).toBe(0)
    expect(warn).toHaveBeenCalledTimes(1)
    warn.mockRestore()
  })

  it('unknown building type -> null, one warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const m = toCityMap({ chunks: [], buildings: [bld('a', { type: 'FACTORY' }), bld('b', { type: 'X', tile_x: 40 })] })
    expect(m.buildingById.get('a')!.type).toBeNull()
    expect(warn).toHaveBeenCalledTimes(1)
    warn.mockRestore()
  })

  it('no warning for clean input; duplicate id keeps first', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const m = toCityMap({ chunks: [chunk()], buildings: [bld('a'), bld('a', { type: 'PUBLIC' })] })
    expect(m.buildingById.size).toBe(1)
    expect(m.buildingById.get('a')!.type).toBe('OFFICE')
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })

  it('anchor ownership: boundary building only in anchor chunk', () => {
    const bs = [bld('edge', { tile_x: 31, tile_y: 0, width: 3 }), bld('far', { tile_x: 100, tile_y: 40 })]
    const m = toCityMap({ chunks: [], buildings: bs })
    expect(m.buildingsByChunk.get('0,0')!.map((b) => b.id)).toEqual(['edge'])
    expect(m.buildingsByChunk.has('1,0')).toBe(false)
    expect(m.buildingsByChunk.get('3,1')!.map((b) => b.id)).toEqual(['far'])
    let total = 0
    for (const l of m.buildingsByChunk.values()) total += l.length
    expect(total).toBe(m.buildingById.size)
  })
})
