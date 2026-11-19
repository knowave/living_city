import { chunkKey, isKnownRoad, isKnownTerrain, worldToChunk } from './tiles'
import {
  CHUNK_SIZE,
  TILES_PER_CHUNK,
  type Building,
  type BuildingDTO,
  type BuildingType,
  type ChunkDTO,
  type Chunk,
  type ChunkKey,
  type CityMap,
} from './types'

const BUILDING_TYPES: readonly string[] = ['RESIDENTIAL', 'COMMERCIAL', 'OFFICE', 'PUBLIC']

export function toChunk(dto: ChunkDTO, onUnknown: (count: number) => void): Chunk {
  if (dto.chunk_size !== CHUNK_SIZE) throw new Error(`unsupported chunk_size ${dto.chunk_size}`)
  if (dto.terrain_tiles.length !== TILES_PER_CHUNK || dto.road_tiles.length !== TILES_PER_CHUNK) {
    throw new Error(`chunk ${dto.chunk_x},${dto.chunk_y}: tile arrays must have ${TILES_PER_CHUNK} entries`)
  }
  let unknown = 0
  const terrainTiles = dto.terrain_tiles.map((v) => {
    if (isKnownTerrain(v)) return v
    unknown++
    return 0
  })
  const roadTiles = dto.road_tiles.map((v) => {
    if (isKnownRoad(v)) return v
    unknown++
    return 0
  })
  if (unknown > 0) onUnknown(unknown)
  return {
    id: dto.id,
    worldId: dto.world_id,
    chunkX: dto.chunk_x,
    chunkY: dto.chunk_y,
    chunkSize: dto.chunk_size,
    terrainTiles,
    roadTiles,
    schemaVersion: dto.schema_version,
    revision: dto.revision,
  }
}

export function toBuilding(dto: BuildingDTO, onUnknown: () => void): Building {
  const known = BUILDING_TYPES.includes(dto.type)
  if (!known) onUnknown()
  return {
    id: dto.id,
    worldId: dto.world_id,
    type: known ? (dto.type as BuildingType) : null,
    tileX: dto.tile_x,
    tileY: dto.tile_y,
    width: dto.width,
    height: dto.height,
    capacity: dto.capacity,
    occupiedCapacity: dto.occupied_capacity,
    status: dto.status,
  }
}

export function toCityMap(
  input: { chunks: ChunkDTO[]; buildings: BuildingDTO[] },
  warn: (msg: string) => void = console.warn,
): CityMap {
  let unknownTiles = 0
  let unknownTypes = 0
  const chunks = new Map<ChunkKey, Chunk>()
  for (const dto of input.chunks) {
    chunks.set(
      chunkKey(dto.chunk_x, dto.chunk_y),
      toChunk(dto, (n) => (unknownTiles += n)),
    )
  }
  const buildingById = new Map<string, Building>()
  const buildingsByChunk = new Map<ChunkKey, Building[]>()
  for (const dto of input.buildings) {
    if (buildingById.has(dto.id)) continue // dedupe: keep first
    const b = toBuilding(dto, () => unknownTypes++)
    buildingById.set(b.id, b)
    const { chunkX, chunkY } = worldToChunk(b.tileX, b.tileY)
    const key = chunkKey(chunkX, chunkY)
    const list = buildingsByChunk.get(key)
    if (list) list.push(b)
    else buildingsByChunk.set(key, [b])
  }
  if (unknownTiles > 0) warn(`map: ${unknownTiles} unknown tile value(s) replaced with defaults`)
  if (unknownTypes > 0) warn(`map: ${unknownTypes} building(s) with unknown type`)
  const worldId = input.chunks[0]?.world_id ?? input.buildings[0]?.world_id ?? ''
  return { worldId, chunks, buildingById, buildingsByChunk }
}
