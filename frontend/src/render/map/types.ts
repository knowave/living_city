export const CHUNK_SIZE = 32
export const CHUNKS_PER_SIDE = 16
export const TILES_PER_CHUNK = 1024
export const TILE_SCHEMA_VERSION = 1

export type BuildingType = 'RESIDENTIAL' | 'COMMERCIAL' | 'OFFICE' | 'PUBLIC'

// DTO: backend ChunkRead / Building, snake_case 1:1
export interface ChunkDTO {
  id: string
  world_id: string
  chunk_x: number
  chunk_y: number
  chunk_size: number
  terrain_tiles: number[]
  road_tiles: number[]
  schema_version: number
  revision: number
}

export interface BuildingDTO {
  id: string
  world_id: string
  type: string // trust boundary: mapper validates
  tile_x: number
  tile_y: number
  width: number
  height: number
  capacity: number
  occupied_capacity: number
  status: string
}

export interface Chunk {
  id: string
  worldId: string
  chunkX: number
  chunkY: number
  chunkSize: number
  terrainTiles: number[]
  roadTiles: number[]
  schemaVersion: number
  revision: number
}

export interface Building {
  id: string
  worldId: string
  type: BuildingType | null // null = unknown type, default style
  tileX: number
  tileY: number
  width: number
  height: number
  capacity: number
  occupiedCapacity: number
  status: string
}

export type ChunkKey = `${number},${number}`

export interface CityMap {
  worldId: string
  chunks: Map<ChunkKey, Chunk>
  buildingById: Map<string, Building>
  buildingsByChunk: Map<ChunkKey, Building[]> // render ownership = anchor chunk only
}
